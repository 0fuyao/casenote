"""Bonsai 2 (PrismML) client: a local OpenAI-compatible server on localhost:8080."""

from __future__ import annotations

import json
import os
import re

import httpx

BASE = os.environ.get("BONSAI_URL", "http://localhost:8080/v1")
_model_id: str | None = None

# Sampling presets from the Bonsai 2 model card (see the hackathon sample README).
FAST = dict(temperature=0.7, top_p=0.8, top_k=20, min_p=0, presence_penalty=1.5,
            chat_template_kwargs={"enable_thinking": False})
STRICT = dict(temperature=0.2, top_p=0.8, top_k=20, min_p=0, presence_penalty=1.0,
              chat_template_kwargs={"enable_thinking": False})


def model_id() -> str:
    global _model_id
    if _model_id is None:
        r = httpx.get(f"{BASE}/models", timeout=10).json()
        loaded = [m["id"] for m in r["data"] if m.get("loaded", True)]
        _model_id = loaded[0]
    return _model_id


def chat(messages, max_tokens=600, preset=FAST, timeout=180) -> str:
    body = {"model": model_id(), "messages": messages, "max_tokens": max_tokens, **preset}
    r = httpx.post(f"{BASE}/chat/completions", json=body, timeout=timeout)
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"] or ""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def available() -> bool:
    try:
        model_id()
        return True
    except Exception:
        return False


def _json_block(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def extract_fields(doc_type: str, ocr_text: str, keys: list[str]) -> dict | None:
    """Ask Bonsai to read OCR text into JSON. Validated by the caller."""
    prompt = (
        f"Below is OCR text from a {doc_type.upper()} document. Extract these fields: {', '.join(keys)}.\n"
        "Rules: copy values exactly as printed; dates as MM/DD/YYYY; use null if a field is absent; "
        "the 'Surname'/'Last' label gives surname, the 'Given'/'First' label gives given_names. "
        "Reply with ONE JSON object and nothing else.\n\nOCR TEXT:\n" + ocr_text[:3000]
    )
    try:
        out = chat([{"role": "user", "content": prompt}], max_tokens=300, preset=STRICT, timeout=120)
    except Exception:
        return None
    return _json_block(out)


SYSTEM_QA = """You are CaseNote's AI immigration assistant. You run fully offline on the user's own Mac.
You give general legal information, not legal advice.
Rules:
1. Answer ONLY from the PROFILE, FLAGGED ISSUES, STATUS PATH and RULE LIBRARY below. Never invent rules, dates or numbers.
2. When you rely on a rule, cite its id at the end of the sentence, like [R1].
3. Answer in English. Start with a one-line bottom line, then 2-3 concrete next steps. Max 110 words.
4. Never mention possible outcomes such as refusal, denial, deportation or risk. Take next steps only from the suggestions in FLAGGED ISSUES.
5. Do not derive new date requirements; restate the rule library wording (e.g. "the travel signature is valid for one year").
6. For personal judgement calls or anything the rule library does not cover, say "Have an attorney review this."

Format example:
Bottom line: Your I-20 travel signature stopped being valid on <date from FLAGGED ISSUES> [R1].
Next steps:
1. ...
2. ...
Have an attorney review: <one specific question to ask the attorney>
"""


def answer(question: str, profile: dict, issues: list[dict], rules: list[dict], path: list[dict] | None = None) -> str:
    kb = "\n".join(f"[{r['id']}] {r['en']} (source: {r['source_name']})" for r in rules)
    iss = "\n".join(f"- [{i['rule']}] {i['title_en']}: {i['detail_en']} Suggested step: {i['action_en']}" for i in issues) or "(none)"
    prof = json.dumps(profile, ensure_ascii=False)
    pth = "\n".join(f"- {p['stage']}: {p['when']}. {p['detail']}" + (f" [{p['rule']}]" if p['rule'] else "") for p in (path or [])) or "(none)"
    msgs = [
        {"role": "system", "content": SYSTEM_QA},
        {"role": "user", "content": f"PROFILE: {prof}\n\nFLAGGED ISSUES:\n{iss}\n\nSTATUS PATH (dates computed from the documents):\n{pth}\n\nRULE LIBRARY:\n{kb}\n\nUSER QUESTION (may be in any language; answer in English): {question}"},
    ]
    return chat(msgs, max_tokens=400, preset=STRICT)


def lawyer_summary(profile: dict, issues: list[dict], qa: list[dict]) -> str:
    iss = "\n".join(f"- {i['title_en']}: {i['detail_en']}" for i in issues) or "- none"
    qas = "\n".join(f"Q: {q['q']}\nA: {q['a']}" for q in qa) or "none"
    msgs = [{"role": "user", "content": (
        "You are preparing an intake note for a licensed US immigration attorney. "
        "Write exactly 4 short bullet points in English, one per line, starting with '- ': "
        "(1) who the client is (name, nationality, school, status); (2) the flagged issues, using their titles VERBATIM; "
        "(3) what the client asked; (4) what the attorney should verify first. "
        "Use only the facts below. Do not change any wording of an issue title, do not relabel ID numbers, "
        "and do not give legal advice.\n\n"
        f"PROFILE: {json.dumps(profile)}\nFLAGGED ISSUES:\n{iss}\nCLIENT Q&A (translated if needed):\n{qas}")}]
    return chat(msgs, max_tokens=350, preset=STRICT)


def consult_notes(lines: list[dict], profile: dict, issues: list[dict]) -> str:
    """Attorney-ready notes from a diarized consultation transcript."""
    tx = "\n".join(f"{l['speaker']}: {l['text']}" for l in lines)[:4000]
    iss = "\n".join(f"- {i['title_en']}" for i in issues) or "- none"
    msgs = [{"role": "user", "content": (
        "Below is a speaker-labelled transcript of a meeting between an immigration attorney and a client, "
        "plus issues already flagged from the client's documents. Write 3 to 5 short bullet points in English, "
        "each starting with '- ': facts the client stated, what the attorney said they will do, and open questions. "
        "Name speakers as in the transcript. Use only what is said; do not add legal conclusions.\n\n"
        f"FLAGGED ISSUES:\n{iss}\n\nTRANSCRIPT:\n{tx}")}]
    return chat(msgs, max_tokens=300, preset=STRICT)
