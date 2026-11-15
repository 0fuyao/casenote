"""CaseNote local server. Everything runs on this Mac; nothing is sent anywhere.

Run:  .venv/bin/python -m uvicorn app.server:app --port 8765
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import threading
import uuid
from datetime import date, timedelta
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import extract as ex
from . import llm, packet, rules, speech
from .ocr import ocr_image

ROOT = Path(__file__).resolve().parents[1]
UPLOADS = ROOT / "data/uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="CaseNote")
STATE: dict = {"docs": {}, "qa": [], "order": [], "gen": 0, "consult": None}
VAULT = ROOT / "data/vault.json"  # the local document vault: stays in this folder on this Mac


def _save():
    VAULT.write_text(json.dumps({"docs": STATE["docs"], "order": STATE["order"], "consult": STATE["consult"]}))


def _load():
    if VAULT.exists():
        try:
            v = json.loads(VAULT.read_text())
            docs = {k: d for k, d in v.get("docs", {}).items() if Path(d.get("path", "")).exists()}
            STATE.update({"docs": docs, "order": [i for i in v.get("order", []) if i in docs], "consult": v.get("consult")})
        except (OSError, ValueError):
            pass


_load()
OCR_LOCK = threading.Lock()


def _return_date(s: str | None) -> date:
    try:
        return date.fromisoformat(s) if s else date.today() + timedelta(days=1)
    except ValueError:
        return date.today() + timedelta(days=1)


@app.get("/api/status")
def status():
    return {
        "bonsai": llm.available(),
        "bonsai_model": llm.model_id() if llm.available() else None,
        "argmax_cli": Path(speech.CLI).exists(),
        "asr_model": speech.ASR_MODEL.exists(),
        "tts_model": speech.TTS_MODELS.exists(),
        "today": date.today().isoformat(),
    }


def _process(path: Path) -> dict:
    with OCR_LOCK:
        lines = ocr_image(path)
    return ex.extract(lines)


@app.post("/api/docs")
async def upload(file: UploadFile = File(...)):
    doc_id = uuid.uuid4().hex[:8]
    suffix = Path(file.filename or "doc.png").suffix.lower() or ".png"
    path = UPLOADS / f"{doc_id}{suffix}"
    with path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    gen = STATE["gen"]
    try:
        result = await asyncio.to_thread(_process, path)
    except Exception as e:  # keep the demo alive on a bad file
        raise HTTPException(500, f"Could not read this file: {e}")
    result.pop("text", None)
    if gen != STATE["gen"]:  # the session was reset while this file was processing
        raise HTTPException(409, "Session was reset; result discarded")
    result.update({"id": doc_id, "filename": file.filename, "image": f"/api/docs/{doc_id}/image"})
    STATE["docs"][doc_id] = {**result, "path": str(path)}
    STATE["order"].append(doc_id)
    _save()
    return result


@app.get("/api/vault")
def vault():
    """Documents saved on this Mac from earlier sessions."""
    docs = [{k: v for k, v in STATE["docs"][i].items() if k != "path"} for i in STATE["order"]]
    return {"docs": docs, "consult": STATE["consult"]}


@app.get("/api/docs/{doc_id}/image")
def doc_image(doc_id: str):
    d = STATE["docs"].get(doc_id)
    if not d:
        raise HTTPException(404)
    return FileResponse(d["path"])


@app.delete("/api/docs/{doc_id}")
def delete_doc(doc_id: str):
    STATE["docs"].pop(doc_id, None)
    STATE["order"] = [i for i in STATE["order"] if i != doc_id]
    _save()
    return {"ok": True}


@app.get("/api/case")
def case(return_date: str | None = None):
    rd = _return_date(return_date)
    docs = STATE["docs"]
    profile = rules.build_profile(docs)
    return {"return_date": rd.isoformat(), "profile": profile, "issues": rules.check(docs, rd),
            "timeline": rules.timeline(profile, rd) if docs else [], "path": rules.path(profile),
            "rules": rules.RULES}


@app.get("/api/calendar.ics")
def calendar(return_date: str | None = None):
    rd = _return_date(return_date)
    events = rules.timeline(rules.build_profile(STATE["docs"]), rd)
    return Response(rules.ics(events), media_type="text/calendar",
                    headers={"Content-Disposition": 'attachment; filename="CaseNote_deadlines.ics"'})


@app.post("/api/consult")
async def consult(audio: UploadFile = File(...), return_date: str | None = Form(None)):
    raw = UPLOADS / f"consult_{uuid.uuid4().hex[:6]}{Path(audio.filename or 'c.webm').suffix or '.webm'}"
    with raw.open("wb") as f:
        shutil.copyfileobj(audio.file, f)
    wav = await asyncio.to_thread(speech.to_wav, raw)
    segs, turns = await asyncio.gather(asyncio.to_thread(speech.transcribe_segments, wav),
                                       asyncio.to_thread(speech.diarize, wav))
    lines = speech.merge(segs, turns)
    rd = _return_date(return_date)
    docs = STATE["docs"]
    try:
        notes = await asyncio.to_thread(llm.consult_notes, lines, rules.build_profile(docs), rules.check(docs, rd))
    except Exception:
        notes = ""
    STATE["consult"] = {"lines": lines, "notes": notes, "speakers": len({l["speaker"] for l in lines})}
    _save()
    raw.unlink(missing_ok=True); wav.unlink(missing_ok=True)  # keep the notes, not the audio
    return STATE["consult"]


@app.post("/api/ask")
async def ask(audio: UploadFile | None = File(None), text: str | None = Form(None), return_date: str | None = Form(None)):
    transcript_ms = None
    question = (text or "").strip()
    if audio is not None:
        raw = UPLOADS / f"q_{uuid.uuid4().hex[:6]}{Path(audio.filename or 'q.webm').suffix or '.webm'}"
        with raw.open("wb") as f:
            shutil.copyfileobj(audio.file, f)
        wav = await asyncio.to_thread(speech.to_wav, raw)
        question = await asyncio.to_thread(speech.transcribe, wav, None)  # auto-detect language
        raw.unlink(missing_ok=True); wav.unlink(missing_ok=True)  # don't keep voice recordings
    if not question:
        raise HTTPException(400, "No question heard")
    rd = _return_date(return_date)
    docs = STATE["docs"]
    profile, issues = rules.build_profile(docs), rules.check(docs, rd)
    answer = await asyncio.to_thread(llm.answer, question, profile, issues, rules.RULES, rules.path(profile))
    cited = sorted(set(re.findall(r"\[(R\d+)\]", answer)))
    if not cited:  # model forgot to cite: attach the rules for the topics discussed
        text = (question + " " + answer).lower()
        topics = [("cpt", "R8"), ("curricular", "R8"), ("stem", "R9"), ("unemploy", "R10"), ("h-1b", "R11"), ("h1b", "R11"),
                  ("lottery", "R11"), ("green card", "R12"), ("permanent", "R12"), ("opt", "R7"), ("travel signature", "R1"),
                  ("i-94", "R2"), ("visa", "R4"), ("passport", "R5"), ("grace", "R6")]
        cited = sorted({r for k, r in topics if k in text}, key=lambda r: int(r[1:])) or sorted({i["rule"] for i in issues})
        if cited:
            answer += "\n\nBasis: " + " ".join(f"[{c}]" for c in cited)
    item = {"q": question, "a": answer, "cited": cited}
    STATE["qa"].append(item)
    return item


class SpeakReq(BaseModel):
    text: str


@app.post("/api/speak")
def speak(req: SpeakReq):
    clean = re.sub(r"\[R\d+\]", "", req.text)
    clean = re.sub(r"[*#`>]", "", clean).strip()
    speech.speak_live(clean[:600], "english")
    return {"ok": True}


@app.post("/api/speak/stop")
def speak_stop():
    speech.stop()
    return {"ok": True}


@app.post("/api/packet")
async def make_packet(return_date: str | None = Form(None)):
    rd = _return_date(return_date)
    docs = STATE["docs"]
    profile, issues = rules.build_profile(docs), rules.check(docs, rd)
    try:
        summary = await asyncio.to_thread(llm.lawyer_summary, profile, issues, STATE["qa"])
    except Exception:
        summary = "- Summary unavailable (local model offline); see flagged issues below."
    pdf = packet.build(profile, issues, STATE["qa"], summary, rd, STATE.get("consult"), rules.path(profile))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="CaseNote_case_packet.pdf"'})


@app.post("/api/reset")
def reset():
    """Forget everything: delete uploaded images, recordings and the vault file."""
    STATE.update({"docs": {}, "qa": [], "order": [], "gen": STATE["gen"] + 1, "consult": None})
    for f in UPLOADS.glob("*"):
        f.unlink(missing_ok=True)
    VAULT.unlink(missing_ok=True)
    return {"ok": True}


app.mount("/samples", StaticFiles(directory=ROOT / "samples"), name="samples")
app.mount("/", StaticFiles(directory=ROOT / "static", html=True), name="static")
