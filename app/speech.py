"""Argmax on-device speech: WhisperKit transcription + TTSKit (Qwen3-TTS) speech.

Uses the Argmax open-source CLI (`brew install whisperkit-cli`), pointed at
model folders on disk so it never needs the network.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = shutil.which("whisperkit-cli") or "/opt/homebrew/bin/whisperkit-cli"
ASR_MODEL = Path(os.environ.get(
    "CASENOTE_ASR_MODEL",
    ROOT / "models/argmax/models/argmaxinc/whisperkit-coreml/openai_whisper-large-v3-v20240930_turbo_632MB"))
ASR_TOKENIZER_DIR = ROOT / "models/argmax"
HF = Path.home() / "Documents/huggingface/models"
TTS_MODELS = Path(os.environ.get("CASENOTE_TTS_MODELS", HF / "argmaxinc/ttskit-coreml"))
TTS_TOKENIZER = Path(os.environ.get("CASENOTE_TTS_TOKENIZER", HF / "Qwen/Qwen3-0.6B"))
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"


def to_wav(src: Path) -> Path:
    """Browser recordings arrive as webm/ogg; WhisperKit wants a plain audio file."""
    dst = src.with_name(src.stem + "_16k.wav")
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(src), "-ar", "16000", "-ac", "1", str(dst)], check=True)
    return dst


def transcribe(audio: Path, language: str = "zh") -> str:
    cmd = [CLI, "transcribe", "--audio-path", str(audio), "--model-path", str(ASR_MODEL),
           "--download-tokenizer-path", str(ASR_TOKENIZER_DIR), "--without-timestamps"]
    if language:
        cmd += ["--language", language]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    lines = [l.strip() for l in out.stdout.splitlines() if l.strip()]
    if out.returncode != 0 or not lines:
        raise RuntimeError(out.stderr[-500:] or "transcription failed")
    return lines[-1]


_speaker: subprocess.Popen | None = None


def speak(text: str, language: str = "chinese") -> Path:
    """Synthesize to a wav file the browser can play."""
    out = Path(tempfile.mkdtemp(prefix="casenote_tts_")) / "answer"
    cmd = [CLI, "tts", "--text", text, "--language", language, "--speaker", "vivian",
           "--models-path", str(TTS_MODELS), "--tokenizer", str(TTS_TOKENIZER),
           "--output-path", str(out), "--output-format", "wav"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    wav = out.with_suffix(".wav")
    if r.returncode != 0 or not wav.exists():
        raise RuntimeError(r.stderr[-500:] or "tts failed")
    return wav


def speak_live(text: str, language: str = "english") -> None:
    """Stream speech straight to the Mac's speakers (starts talking sooner)."""
    global _speaker
    if _speaker and _speaker.poll() is None:
        _speaker.terminate()
    voice = "vivian" if language == "chinese" else "ryan"
    _speaker = subprocess.Popen([CLI, "tts", "--text", text, "--language", language, "--speaker", voice,
                                 "--models-path", str(TTS_MODELS), "--tokenizer", str(TTS_TOKENIZER), "--play",
                                 "--output-path", str(Path(tempfile.gettempdir()) / "casenote_live")],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def stop() -> None:
    if _speaker and _speaker.poll() is None:
        _speaker.terminate()


# ---------- attorney consult: transcription with timestamps + speaker diarization ----------
import json
import re as _re

DIAR_MODEL = ROOT / "models/argmax/models/argmaxinc/speakerkit-coreml"


def transcribe_segments(audio: Path) -> list[dict]:
    """WhisperKit transcription with segment timestamps (language auto-detected)."""
    rep = Path(tempfile.mkdtemp(prefix="casenote_rep_"))
    cmd = [CLI, "transcribe", "--audio-path", str(audio), "--model-path", str(ASR_MODEL),
           "--download-tokenizer-path", str(ASR_TOKENIZER_DIR), "--report", "--report-path", str(rep)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-500:] or "transcription failed")
    segs = []
    for js in rep.glob("*.json"):
        data = json.loads(js.read_text())
        for s in data.get("segments", []):
            text = _re.sub(r"<\|[^|]*\|>", "", s.get("text", "")).strip()
            if text:
                segs.append({"start": float(s.get("start", 0)), "end": float(s.get("end", 0)), "text": text})
    return sorted(segs, key=lambda s: s["start"])


def diarize(audio: Path, num_speakers: int | None = None) -> list[dict]:
    """Argmax SpeakerKit diarization -> [{start, end, speaker}] from RTTM."""
    rttm = Path(tempfile.mkdtemp(prefix="casenote_rttm_")) / "out.rttm"
    cmd = [CLI, "diarize", "--audio-path", str(audio), "--rttm-path", str(rttm), "--model-path", str(DIAR_MODEL)]
    if num_speakers:
        cmd += ["--num-speakers", str(num_speakers)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0 or not rttm.exists():
        raise RuntimeError(r.stderr[-500:] or "diarization failed")
    turns = []
    for line in rttm.read_text().splitlines():
        p = line.split()
        if len(p) >= 8 and p[0] == "SPEAKER":
            st, du = float(p[3]), float(p[4])
            turns.append({"start": st, "end": st + du, "speaker": p[7]})
    return turns


def merge(segs: list[dict], turns: list[dict]) -> list[dict]:
    """Give each transcript segment the speaker with the most overlap; merge consecutive lines."""
    names: dict[str, str] = {}
    out: list[dict] = []
    for s in segs:
        best, ov = None, 0.0
        for t in turns:
            o = min(s["end"], t["end"]) - max(s["start"], t["start"])
            if o > ov:
                best, ov = t["speaker"], o
        if best is None and turns:  # no overlap: nearest turn
            best = min(turns, key=lambda t: abs(t["start"] - s["start"]))["speaker"]
        label = names.setdefault(best or "?", f"Speaker {len(names) + 1}")
        if out and out[-1]["speaker"] == label:
            out[-1]["text"] += " " + s["text"]
            out[-1]["end"] = s["end"]
        else:
            out.append({"speaker": label, "start": s["start"], "end": s["end"], "text": s["text"]})
    return out
