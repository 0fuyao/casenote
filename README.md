# CaseNote — an on-device AI immigration assistant

**Cornell Local AI Hackathon · theme: RECREATE.** Cloud "AI immigration lawyer" apps want you to upload your passport. CaseNote recreates that experience **fully on a Mac with WiFi off**: your passport, visa, I-20 and I-94 never leave the machine.

Picture an international student on a 14-hour flight with no internet, two hours before landing. CaseNote reads their documents, cross-checks them against official rules, and flags problems right on the page with a citation for each one. It answers spoken questions in English or Chinese, and hands a clean English case packet to a real attorney.

## What it does

1. **Reads documents on-device.** Apple Vision OCR runs locally. Passport and visa MRZ lines are parsed and verified with ICAO 9303 check digits. **PrismML Bonsai 2 9B** reads the I-20 and I-94 into structured fields.
2. **Cross-checks with deterministic rules.** Each rule cites an official DHS / ICE / CBP page. Each problem is highlighted at its exact location on the original document.
3. **AI immigration assistant.** **Argmax WhisperKit** transcribes a spoken question (language auto-detected). **Bonsai 9B** answers only from the user's profile, the flagged issues and the rule library, with `[R#]` citations. **Argmax TTSKit** (Qwen3-TTS) reads the answer aloud.
4. **Deadlines.** Key dates come from the documents: travel signature validity, visa and passport expiry, the OPT window and the grace period. Each is tied to its rule and can be exported to Apple Calendar as an `.ics` file with 30-day reminders.
5. **Attorney meeting.** Record a consultation. **Argmax WhisperKit** transcribes it and **Argmax SpeakerKit** separates the speakers. **Bonsai 9B** writes fact-only notes.
6. **Attorney hand-off.** One click builds an English PDF case packet: an AI intake summary, the flagged issues with sources and next steps, the profile, the client's Q&A, and the meeting transcript.

The demo uses four **SPECIMEN** documents with fictional data (`tools/make_specimens.py`). Two problems are planted: an I-20 travel signature that is 14 months old, and an I-94 with the surname and given name swapped.

## Where the sponsor models are used

| Step | Model / tool | Runs on |
|---|---|---|
| I-20 / I-94 field extraction | PrismML Bonsai 2 9B (MLX 2-bit, ~3.4 GB) via `mlx_vlm.server` | Mac GPU |
| Q&A grounded in rules, with citations | PrismML Bonsai 2 9B | Mac GPU |
| Attorney intake summary | PrismML Bonsai 2 9B | Mac GPU |
| Speech-to-text (EN / ZH) | Argmax WhisperKit, Whisper large-v3 turbo (`whisperkit-cli transcribe`) | Neural Engine |
| Text-to-speech | Argmax TTSKit, Qwen3-TTS 0.6B (`whisperkit-cli tts`) | Neural Engine |
| Speaker diarization (attorney meeting) | Argmax SpeakerKit (`whisperkit-cli diarize`) | Neural Engine |
| Meeting notes | PrismML Bonsai 2 9B | Mac GPU |
| OCR | Apple Vision | on-device |

Design principle: **deterministic where possible, AI where needed.** MRZ check digits and date rules are code. Bonsai handles language: reading semi-structured forms, explaining, and summarizing. It is never the only source of a legal fact.

## Rules (sources checked 2026-11-15)

| ID | Rule | Source |
|---|---|---|
| R1 | F-1 I-20 travel endorsement is valid for one year | [Study in the States: DSOs and the Form I-20](https://studyinthestates.dhs.gov/schools/report/dsos-and-the-form-i-20) |
| R2 | Identity data should agree across documents; CBP Deferred Inspection corrects entry-time I-94 errors | [CBP: Deferred Inspection Sites](https://www.cbp.gov/contact/ports/deferred-inspection-sites) |
| R3 | I-94 class F-1; fixed Admit Until Date replaces D/S for admissions after Sept 15, 2026 | [Study in the States: Elimination of D/S FAQ](https://studyinthestates.dhs.gov/elimination-of-duration-of-status-frequently-asked-questions) |
| R4 | Re-entry needs a valid F-1 visa (automatic revalidation exception) | [ICE SEVP: Travel](https://www.ice.gov/sevis/travel) |
| R5 | Passport valid 6 months past re-entry; China is not on the Six-Month Club list | [ICE SEVP: Travel](https://www.ice.gov/sevis/travel) |
| R6 | 60-day grace period after program end (30 days under the new rule) | [Study in the States: Maintaining Status](https://studyinthestates.dhs.gov/students/maintaining-status) |
| R7 | OPT I-765 window: 90 days before to 60 days after program end | [Study in the States: Practical Training](https://studyinthestates.dhs.gov/students/work/applying-for-practical-training) |

## Run it

Requirements: Apple Silicon Mac, macOS 15+, Python 3.10+, Homebrew.

```bash
./setup.sh      # once, with internet: venv, Bonsai 9B, Argmax CLI + models, sample docs
./run.sh        # then turn WiFi off; opens http://localhost:8765
```

In the app, click **Use sample documents** and ask a question with the mic. Under Attorney meeting, try **use the sample meeting** (synthetic voices).

## Project layout

```
app/ocr.py       Apple Vision OCR with bounding boxes
app/mrz.py       ICAO 9303 TD3 / MRV-A parse and check digits
app/extract.py   document classification, Bonsai field extraction, validation
app/rules.py     rule library + deterministic checks + per-issue next steps
app/llm.py       Bonsai client (OpenAI-compatible, localhost:8080)
app/speech.py    Argmax WhisperKit transcription + TTSKit speech
app/packet.py    attorney case packet (PDF, ReportLab)
app/server.py    FastAPI app
static/index.html  single-file UI, no CDN (works offline)
```

## Important limits

- CaseNote gives **general legal information, not legal advice**. Personal conclusions are routed to a licensed attorney.
- The demo covers F-1 re-entry only. Rules must be reviewed by an immigration attorney before real use.
- Specimen documents are simplified mock-ups with fictional data, watermarked on every page. Never use them as real documents.
- Built during the hackathon with help from Claude Code (not eligible for the "Locally Made" subtrack).
