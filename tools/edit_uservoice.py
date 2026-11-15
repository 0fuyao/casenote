"""Cut the demo to the creator's own voiceover, with pauses removed and English subtitles.

  .venv/bin/python tools/edit_uservoice.py video/take3 video/uservo/raw.m4a
Uses the last take of any repeated line; subtitle text is the spoken words, cleaned of
transcription errors. Outputs <take>/CaseNote_demo_voice.mp4 and .srt.
"""

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from edit_video import FPS, H, NAVY, SF, W, WHITE, card, dur  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GAP = 0.05       # gap left where a pause was removed (s)
PAD = 0.05       # keep this much around each speech span (s)
MAX_LEN = 119.4  # competition limit is 2:00; leave a little room

# (orig start, orig end, subtitle text, scene)
LINES = [
    (0.06, 1.18, "Hi, I'm Fuyao.", "A"),
    (1.28, 5.60, "Like many international students, I have trouble managing all my documents", "A"),
    (6.26, 9.16, "and sending them to the International Student Center.", "A"),
    (10.02, 15.76, "And I can't upload these files to online agents because I'm worried about data security.", "A"),
    (16.44, 21.30, "So, CaseNote is an AI immigration assistant for international students.", "A2"),
    (21.92, 27.32, "It runs entirely on your Mac with WiFi off, so your passport and visa never leave your computer.", "A2"),
    (35.80, 41.92, "On the left, you can add your passport, visa, I-20 and I-94 here.", "B"),
    (42.48, 43.66, "Apple Vision reads the text.", "B"),
    (44.12, 48.14, "The passport and visa are verified with their machine-readable check digits.", "B"),
    (48.80, 53.20, "And PrismML's Bonsai 9B reads the I-20 and I-94 into fields.", "B"),
    (55.16, 61.14, "CaseNote also checks every document against official DHS, ICE and CBP rules.", "C"),
    (61.74, 63.84, "Here it finds two problems. You can see here:", "C"),
    (64.50, 68.42, "the travel signature has expired, and the I-94 has the names swapped.", "C"),
    (68.94, 71.60, "Each one is highlighted on the document and linked to its source.", "C"),
    (71.60, 75.66, "It also maps your path, with dates from your own I-20:", "D"),
    (76.01, 80.78, "when CPT opens, your OPT filing window, the STEM OPT extension, the H-1B registration", "D"),
    (81.40, 86.64, "seasons and cap-gap, and the green card routes to discuss with a lawyer, as we can connect you with one.", "D"),
    (87.34, 88.64, "Each stage cites its rule.", "D"),
    (0.26, 2.56, "And now comes the AI lawyer part.", "E", 1),
    (3.10, 10.26, "You can ask the AI lawyer anything, and it will reply with a simulated human voice, using voice AI.", "E", 1),
    (89.46, 92.92, "You can ask anything in English or in your native language.", "E"),
    (93.64, 96.60, "Argmax WhisperKit transcribes your voice on the device.", "E"),
    (96.62, 101.80, "Bonsai answers only from your documents and the rules, with citations,", "E"),
    (102.28, 104.74, "and Argmax TTSKit reads the answer back.", "E"),
    (105.04, 110.90, "Every key date then becomes a deadline you can add to Apple Calendar, with a reminder a month ahead.", "F"),
    (112.24, 116.12, "When you meet a lawyer, because we can connect you with a real lawyer,", "G"),
    (116.64, 119.84, "Argmax transcribes the meeting and separates the speakers.", "G"),
    (126.34, 130.16, "You can use one click to build an English case packet for the lawyer to review.", "H"),
    (136.11, 143.87, "And this is how CaseNote becomes your integrated immigration consultant for international students.", "I"),
]


def src_of(line):
    return line[4] if len(line) > 4 else 0


def speech_spans(silences):
    """Kept line intervals minus every detected pause, as (src, orig_start, orig_end) spans."""
    spans = []
    for line in LINES:
        a, b, src = line[0], line[1], src_of(line)
        cur = a - PAD
        for s0, s1 in silences[src]:
            if s1 <= cur or s0 >= b + PAD:
                continue
            if s0 > cur:
                spans.append((src, cur, min(s0 + PAD, b + PAD)))
            cur = max(cur, s1 - PAD)
        if cur < b + PAD:
            spans.append((src, cur, b + PAD))
    return [(sr, max(0, x), y) for sr, x, y in spans if y - x > 0.05]


def main(take: Path, voice: Path, extra: Path, sil_paths=None):
    load = lambda f: [tuple(map(float, l.split())) for l in (ROOT / f).read_text().split("\n") if l.strip()]
    sil_paths = sil_paths or {0: "video/uservo/silences.tsv", 1: "video/uservo/silences_extra.tsv"}
    sil = {k: load(v) for k, v in sil_paths.items()}
    spans = speech_spans(sil)
    newpos, t = [], 0.0
    for sr, a, b in spans:
        newpos.append((sr, a, b, t))
        t += (b - a) + GAP
    total_voice = t
    TEMPO = max(1.0, (total_voice + 0.3) / MAX_LEN)

    def m(x, src=0):  # original time in a source -> new time
        best = None
        for sr, a, b, n in newpos:
            if sr != src:
                continue
            if a <= x <= b:
                return (n + (x - a)) / TEMPO
            if x < a:
                return (n if best is None else best) / TEMPO
            best = n + (b - a)
        return best / TEMPO

    # audio: concatenate spans with short gaps
    filt, labels = [], []
    for i, (sr, a, b, n) in enumerate(newpos):
        filt.append(f"[{sr}:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.02,afade=t=out:st={max(0, b - a - 0.03):.3f}:d=0.03,apad=pad_dur={GAP}[s{i}]")
        labels.append(f"[s{i}]")
    filt.append("".join(labels) + f"concat=n={len(labels)}:v=0:a=1,atempo={TEMPO:.4f},loudnorm=I=-16:TP=-1.5[v]")
    vo_wav = take / "uservoice.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(voice), "-i", str(extra), "-filter_complex", ";".join(filt),
                    "-map", "[v]", "-ar", "48000", str(vo_wav)], check=True)

    log = json.loads((take / "log.json").read_text())
    T = {s["step"]: s["t"] for s in log["steps"]}
    frames = log["frames"]
    ftimes = [f["t"] for f in frames]
    offline = not log.get("online_in_browser", True)

    def frame_at(x):
        lo, hi = 0, len(ftimes) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if ftimes[mid] <= x:
                lo = mid
            else:
                hi = mid - 1
        return take / "frames" / frames[lo]["file"]

    # scene time ranges on the new timeline
    scenes = {}
    for line in LINES:
        a, b, sc, sr = line[0], line[1], line[3], src_of(line)
        s0, s1 = m(a, sr), m(b, sr)
        lo, hi = scenes.get(sc, (s0, s1))
        scenes[sc] = (min(lo, s0), max(hi, s1))
    order = ["A", "A2", "B", "C", "D", "E", "F", "G", "H", "I"]
    bounds, cur = {}, 0.0
    for i, sc in enumerate(order):
        end = scenes[order[i + 1]][0] - 0.05 if i + 1 < len(order) else total_voice / TEMPO + 0.3
        bounds[sc] = (cur, end)
        cur = end

    cards = take / "cards"
    cards.mkdir(exist_ok=True)
    card(cards / "intro.jpg", ["CaseNote"], "An on-device AI immigration assistant for international students")
    card(cards / "end.jpg", ["CaseNote"], "PrismML Bonsai 9B + Argmax  |  everything on-device  |  zero bytes uploaded")
    thumb = next(take.glob("packet.pdf.png"), None)
    pk = cards / "packet.jpg"
    bg = Image.new("RGB", (W, H), NAVY)
    if thumb:
        pg = Image.open(thumb).convert("RGB")
        pg.thumbnail((W - 200, H - 220))
        bg.paste(pg, ((W - pg.width) // 2, 50))
    bg.save(pk, quality=95)

    # cards must match the recorded frame size, or ffmpeg's concat drops them
    fw, fh = Image.open(take / "frames" / frames[0]["file"]).size
    for c in (cards / "intro.jpg", cards / "end.jpg", pk):
        Image.open(c).convert("RGB").resize((fw, fh), Image.LANCZOS).save(c, quality=95)

    clips = {
        "A2": (T["empty"], T["docs_start"], "WiFi off. Everything runs on this Mac." if offline else "Everything runs on this Mac."),
        "B": (T["docs_start"], T["findings"] + 1.0, "Apple Vision OCR  +  MRZ check digits  +  Bonsai 9B"),
        "C": (T["findings"] + 1.0, T["sheet_close"], "7 official DHS, ICE and CBP rules, each one cited"),
        "D": (T["path"], T["path_end"] + 0.8, "Dates computed from your own I-20, each stage cited"),
        "E": (T["rec_start"] - 0.6, T["answer"] + 6.0, "Argmax WhisperKit  >  Bonsai 9B  >  Argmax TTSKit"),
        "F": (T["deadlines"], T["meeting_start"], "Deadlines, exported to Apple Calendar"),
        "G": (T["meeting_start"], T["packet_start"], "Argmax SpeakerKit separates the speakers"),
    }
    concat, overlays = [], []
    for sc in order:
        s0, s1 = bounds[sc]
        D = s1 - s0
        n = max(1, round(D * FPS))
        if sc == "A":
            concat.append((cards / "intro.jpg", n))
        elif sc == "H":
            concat.append((pk, n))
            overlays.append(("cap", s0 + 0.1, s1 - 0.1, "One click: an English case packet for the attorney"))
        elif sc == "I":
            concat.append((cards / "end.jpg", n))
        else:
            a, b, cap = clips[sc]
            speed = (b - a) / D
            for i in range(n):
                concat.append((frame_at(a + (b - a) * i / n), 1))
            if speed > 1.25:
                overlays.append(("speed", s0, s1, f"Sped up {speed:.0f}x" if speed >= 2 else f"Sped up {speed:.1f}x"))
            overlays.append(("cap", s0 + 0.2, s1 - 0.1, cap))
    total = sum(c for _, c in concat) / FPS

    lst = take / "frames_voice.txt"
    with lst.open("w") as f:
        prev, k = None, 0
        for path, c in concat + [(None, 0)]:
            if path == prev:
                k += c
                continue
            if prev is not None:
                f.write(f"file '{prev}'\nduration {k / FPS:.5f}\n")
            prev, k = path, c
        f.write(f"file '{concat[-1][0]}'\n")

    # subtitles: .srt + burned-in images
    def ts(x):
        h, r = divmod(x, 3600)
        mi, s = divmod(r, 60)
        return f"{int(h):02d}:{int(mi):02d}:{s:06.3f}".replace(".", ",")
    subs = [(m(l[0], src_of(l)), m(l[1], src_of(l)), l[2]) for l in LINES]
    # each cue holds 0.15 s past the last word, but never into the next cue
    subs = [(a, min(b + 0.15, subs[i + 1][0] - 0.03) if i + 1 < len(subs) else b + 0.15, t) for i, (a, b, t) in enumerate(subs)]
    srt = take / "CaseNote_demo_voice.srt"
    srt.write_text("\n".join(f"{i + 1}\n{ts(a)} --> {ts(b)}\n{t}\n" for i, (a, b, t) in enumerate(subs)))

    labels_dir = take / "labels_voice"
    labels_dir.mkdir(exist_ok=True)

    def font(size, weight):
        f = ImageFont.truetype(SF, size)
        try:
            f.set_variation_by_name(weight)
        except Exception:
            pass
        return f

    def wrap(text, f, maxw):
        words, lines, line = text.split(), [], ""
        for w in words:
            test = (line + " " + w).strip()
            if f.getlength(test) <= maxw:
                line = test
            else:
                lines.append(line)
                line = w
        lines.append(line)
        return lines

    pngs = []
    for i, (a, b, text) in enumerate(subs):
        f = font(44, "Medium")
        lines = wrap(text, f, 1500)
        lh = 58
        bw = int(max(f.getlength(l) for l in lines)) + 56
        bh = lh * len(lines) + 28
        img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, bw - 1, bh - 1], radius=14, fill=(22, 46, 81, 215))
        for j, l in enumerate(lines):
            d.text(((bw - f.getlength(l)) / 2, 12 + j * lh), l, font=f, fill=WHITE)
        p = labels_dir / f"sub{i:02d}.png"
        img.save(p)
        pngs.append((p, (W - bw) // 2, H - bh - 46, a, b))
    for i, (kind, a, b, text) in enumerate(overlays):
        f = font(32 if kind == "speed" else 34, "Semibold")
        bb = f.getbbox(text)
        bw, bh = bb[2] - bb[0] + 40, 34 + 26
        img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, bw - 1, bh - 1], radius=12, fill=(22, 46, 81, 225))
        d.text((20 - bb[0], 11), text, font=f, fill=WHITE)
        p = labels_dir / f"lab{i:02d}.png"
        img.save(p)
        pngs.append((p, W - bw - 40 if kind == "speed" else 40, 36, a, b))

    # one transparent overlay track: a full-frame RGBA image per change of on-screen text
    cuts = sorted({0.0, total} | {round(a, 3) for *_, a, b in pngs} | {round(b, 3) for *_, a, b in pngs})
    cuts = [c for c in cuts if 0 <= c <= total]
    ovl_list = take / "overlay_track.txt"
    cache = {}
    with ovl_list.open("w") as f:
        for i in range(len(cuts) - 1):
            t0, t1 = cuts[i], cuts[i + 1]
            if t1 - t0 < 1 / FPS:
                continue
            mid = (t0 + t1) / 2
            active = tuple(j for j, (_, _, _, a, b) in enumerate(pngs) if a <= mid < b)
            if active not in cache:
                frame = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                for j in active:
                    p, x, y, _, _ = pngs[j]
                    im = Image.open(p)
                    frame.alpha_composite(im, (int(x), int(y)))
                fp = labels_dir / f"state{len(cache):03d}.png"
                frame.save(fp)
                cache[active] = fp
            f.write(f"file '{cache[active]}'\nduration {t1 - t0:.4f}\n")
        f.write(f"file '{cache[active]}'\n")
    fc = (f"[0:v]scale={W}:{H}:flags=lanczos,fps={FPS}[base];"
          f"[2:v]fps={FPS},format=rgba[ov];[base][ov]overlay=0:0:format=auto[vout]")
    out = take / "CaseNote_demo_voice.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(vo_wav),
                    "-f", "concat", "-safe", "0", "-i", str(ovl_list),
                    "-filter_complex", fc, "-map", "[vout]", "-map", "1:a", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.2f}",
                    "-movflags", "+faststart", str(out)], check=True)
    print(f"tempo {TEMPO:.3f}, voice {total_voice / TEMPO:.1f}s, video {dur(out):.1f}s, spans {len(spans)}, offline take: {offline}")
    for sc in order:
        print(sc, f"{bounds[sc][0]:.1f}-{bounds[sc][1]:.1f}")


if __name__ == "__main__":
    if "--lines" in sys.argv:
        import argparse
        ap = argparse.ArgumentParser()
        ap.add_argument("take"); ap.add_argument("--lines"); ap.add_argument("--voice"); ap.add_argument("--sil")
        a = ap.parse_args()
        LINES[:] = [tuple(x) for x in json.loads((ROOT / a.lines).read_text())]
        SIL_OVERRIDE = {0: a.sil}
        main(ROOT / a.take, ROOT / a.voice, ROOT / a.voice, sil_paths={0: a.sil, 1: a.sil})
    else:
        main(ROOT / sys.argv[1], ROOT / sys.argv[2], ROOT / sys.argv[3])
