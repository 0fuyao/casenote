"""Cut the recorded CaseNote demo into a <=2-minute video with voiceover.

Inputs:  <take>/frames/*.jpg + <take>/log.json  (from tools/record_demo.py)
         video/vo/v_00.wav ... v_07.wav          (Argmax TTS voiceover, one per segment)
Output:  <take>/CaseNote_demo.mp4

Each voiceover segment is laid over its recorded interval. Footage is time-mapped
uniformly to fit; any part played faster than 1.25x gets a visible "Sped up" label.
"""

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FPS = 30
W, H = 1920, 1200
NAVY, WHITE, PALE = (22, 46, 81), (255, 255, 255), (180, 196, 218)
TEMPO = 1.06          # voiceover speed-up
GAP = 0.35            # breath between segments (s)
SF = "/System/Library/Fonts/SFNS.ttf"


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True).stdout.strip())


def card(path, lines, sub=None):
    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)
    big = ImageFont.truetype(SF, 112)
    try:
        big.set_variation_by_name("Bold")  # SF Pro is a variable font
    except Exception:
        pass
    y = H // 2 - (len(lines) * 130) // 2 - (40 if sub else 0)
    for ln in lines:
        d.text((150, y), ln, font=big, fill=WHITE)
        y += 130
    if sub:
        f = ImageFont.truetype(SF, 44)
        d.text((154, y + 30), sub, font=f, fill=PALE)
    img.save(path, quality=95)


def main(take: Path):
    log = json.loads((take / "log.json").read_text())
    frames = log["frames"]
    T = {s["step"]: s["t"] for s in log["steps"]}
    offline = not log.get("online_in_browser", True)
    vo = [ROOT / f"video/vo/v_{i:02d}.wav" for i in range(8)]
    vd = [dur(p) / TEMPO + GAP for p in vo]

    cards = take / "cards"
    cards.mkdir(exist_ok=True)
    card(cards / "c0a.jpg", ["14 hours.", "No WiFi."])
    card(cards / "c0b.jpg", ["One expired", "signature."], "International student, two hours before landing")
    card(cards / "c7.jpg", ["CaseNote"], "PrismML Bonsai 9B + Argmax  |  everything on-device  |  zero bytes uploaded")

    # (kind, source, target duration, caption)
    segs = [
        ("cards", ["c0a.jpg", "c0b.jpg"], vd[0], None),
        ("clip", (T["empty"], T["docs_start"]), vd[1],
         "WiFi off. Everything runs on this Mac." if offline else "Everything runs on this Mac."),
        ("clip", (T["docs_start"], T["findings"] + 1.0), vd[2], "Apple Vision OCR  +  MRZ check digits  +  Bonsai 9B"),
        ("clip", (T["findings"] + 1.0, T["sheet_close"]), vd[3], "7 official DHS, ICE and CBP rules, each one cited"),
        ("clip", (T["sheet_close"], T["answer"] + 6.0), vd[4], "Argmax WhisperKit  >  Bonsai 9B  >  Argmax TTSKit"),
        ("clip", (T["deadlines"], T["meeting_start"]), vd[5], "Deadlines, exported to Apple Calendar"),
        ("clip", (T["meeting_start"], T["packet_start"]), vd[6] * 0.6, "Argmax SpeakerKit separates the speakers"),
        ("packet", None, vd[6] * 0.4, "One click: an English case packet for the attorney"),
        ("cards", ["c7.jpg"], vd[7] + 1.5, None),
    ]

    ftimes = [f["t"] for f in frames]

    def frame_at(t):
        lo, hi = 0, len(ftimes) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if ftimes[mid] <= t:
                lo = mid
            else:
                hi = mid - 1
        return take / "frames" / frames[lo]["file"]

    # page 1 of the packet PDF, rendered by Quick Look, centred on a navy card
    thumb = next(take.glob("packet.pdf.png"), None)
    pk = cards / "packet.jpg"
    bg = Image.new("RGB", (W, H), NAVY)
    if thumb:
        pg = Image.open(thumb).convert("RGB")
        pg.thumbnail((W - 200, H - 160))
        bg.paste(pg, ((W - pg.width) // 2, 60))
    bg.save(pk, quality=95)

    concat, overlays, t_out = [], [], 0.0
    for kind, src, D, cap in segs:
        n = round(D * FPS)
        if kind == "packet":
            concat.append((pk, n))
            overlays.append(("cap", t_out + 0.2, t_out + D - 0.1, cap))
        elif kind == "cards":
            per = n // len(src)
            for i, c in enumerate(src):
                k = per if i < len(src) - 1 else n - per * (len(src) - 1)
                concat.append((cards / c, k))
        else:
            a, b = src
            speed = (b - a) / D
            for i in range(n):
                concat.append((frame_at(a + (b - a) * i / n), 1))
            if speed > 1.25:
                overlays.append(("speed", t_out, t_out + D, f"Sped up {speed:.0f}x" if speed >= 2 else f"Sped up {speed:.1f}x"))
            if cap:
                overlays.append(("cap", t_out + 0.3, t_out + D - 0.2, cap))
        t_out += D

    # concat list (run-length encoded)
    lst = take / "frames.txt"
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

    # audio: each voice clip padded to its segment length; title/end cards included
    starts, acc = [], 0.0
    for kind, src, D, cap in segs:
        starts.append(acc)
        acc += D
    filt, inputs = [], []
    for i, p in enumerate(vo):
        inputs += ["-i", str(p)]
        filt.append(f"[{i}:a]atempo={TEMPO},adelay={int((starts[i] + 0.15) * 1000)}|{int((starts[i] + 0.15) * 1000)}[a{i}]")
    filt.append("".join(f"[a{i}]" for i in range(len(vo))) + f"amix=inputs={len(vo)}:normalize=0,apad,atrim=0:{acc:.3f},loudnorm=I=-16:TP=-1.5[aout]")
    audio = take / "voice.m4a"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filt), "-map", "[aout]",
                    "-c:a", "aac", "-b:a", "192k", str(audio)], check=True)

    # labels rendered with PIL (this ffmpeg has no drawtext), composited with overlay
    labels = take / "labels"
    labels.mkdir(exist_ok=True)
    inputs_v, chain = [], []
    for i, (kind, a, b, text) in enumerate(overlays):
        size = 34 if kind == "speed" else 40
        f = ImageFont.truetype(SF, size)
        try:
            f.set_variation_by_name("Semibold")
        except Exception:
            pass
        pad_x, pad_y = (22, 14) if kind == "speed" else (28, 18)
        bbox = f.getbbox(text)
        bw, bh = bbox[2] - bbox[0] + 2 * pad_x, size + 2 * pad_y
        img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, bw - 1, bh - 1], radius=12, fill=(22, 46, 81, 225))
        d.text((pad_x - bbox[0], pad_y - 2), text, font=f, fill=WHITE)
        png = labels / f"l{i:02d}.png"
        img.save(png)
        inputs_v += ["-loop", "1", "-framerate", str(FPS), "-t", f"{t_out:.2f}", "-i", str(png)]
        x, y = (W - bw - 48, 40) if kind == "speed" else (60, H - bh - 70)
        src = "[base]" if i == 0 else f"[v{i}]"
        chain.append(f"{src}[{i + 2}:v]overlay={x}:{y}:enable='between(t,{a:.2f},{b:.2f})'[v{i + 1}]")
    fc = f"[0:v]scale={W}:{H}:flags=lanczos,fps={FPS}[base];" + ";".join(chain)
    last = f"[v{len(overlays)}]" if overlays else "[base]"
    out = take / "CaseNote_demo.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(audio), *inputs_v,
                    "-filter_complex", fc, "-map", last, "-map", "1:a", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-preset", "medium", "-crf", "20", "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(out)], check=True)
    print(f"wrote {out}  ({dur(out):.1f} s, offline take: {offline})")


if __name__ == "__main__":
    main(ROOT / sys.argv[1])
