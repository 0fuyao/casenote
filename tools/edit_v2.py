"""Demo cut v2: creator's voice + the AI lawyer's own voice, short title, document previews,
and an eased zoom on the chat while the AI lawyer speaks.

  .venv/bin/python tools/edit_v2.py video/take5
Inputs: video/uservo11/{raw.m4a, silences.tsv, lines_v2.json}, video/ai_voice/{voice.wav, lines.json}
"""

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from edit_video import FPS, H, NAVY, SF, W, WHITE, card, dur  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GAP, PAD, MAX_LEN, TITLE = 0.05, 0.05, 119.4, 1.5


def load_tsv(p):
    return [tuple(map(float, l.split())) for l in Path(p).read_text().split("\n") if l.strip()]


def spans_for(lines, silences):
    out = []
    for a, b, _t, _sc, src in lines:
        cur = a - PAD
        for s0, s1 in silences.get(src, []):
            if s1 <= cur or s0 >= b + PAD:
                continue
            if s0 > cur:
                out.append((src, cur, min(s0 + PAD, b + PAD)))
            cur = max(cur, s1 - PAD)
        if cur < b + PAD:
            out.append((src, cur, b + PAD))
    return [(s, max(0, x), y) for s, x, y in out if y - x > 0.05]


def ease(u):  # smoothstep
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def main(take: Path):
    voice = ROOT / "video/uservo11/raw.m4a"
    ai = ROOT / "video/ai_voice/voice.wav"
    lines = [tuple(l) + ((0,) if len(l) == 4 else ()) for l in json.loads((ROOT / "video/uservo11/lines_v2.json").read_text())]
    ai_lines = [tuple(l) + (1,) for l in json.loads((ROOT / "video/ai_voice/lines.json").read_text())]
    # the AI lawyer speaks right after "...TTSKit reads the answer back."
    k = next(i for i, l in enumerate(lines) if "reads the answer back" in l[2]) + 1
    LINES = lines[:k] + ai_lines + lines[k:]
    sil = {0: load_tsv(ROOT / "video/uservo11/silences.tsv"), 1: load_tsv(ROOT / "video/ai_voice/silences.tsv")}

    spans = spans_for(LINES, sil)
    pos, t = [], 0.0
    for sr, a, b in spans:
        pos.append((sr, a, b, t))
        t += (b - a) + GAP
    tempo = max(1.0, (t + 0.3) / MAX_LEN)
    total_voice = t / tempo

    def m(x, src):
        best = None
        for sr, a, b, n in pos:
            if sr != src:
                continue
            if a <= x <= b:
                return (n + x - a) / tempo
            if x < a:
                return (n if best is None else best) / tempo
            best = n + (b - a)
        return best / tempo

    filt, lab = [], []
    for i, (sr, a, b, n) in enumerate(pos):
        filt.append(f"[{sr}:a]aresample=48000,aformat=channel_layouts=mono,atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,"
                    f"afade=t=in:d=0.02,afade=t=out:st={max(0, b - a - 0.03):.3f}:d=0.03,apad=pad_dur={GAP}[s{i}]")
        lab.append(f"[s{i}]")
    filt.append("".join(lab) + f"concat=n={len(lab)}:v=0:a=1,atempo={tempo:.4f},loudnorm=I=-16:TP=-1.5[v]")
    vo = take / "voice_v2.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(voice), "-i", str(ai), "-filter_complex", ";".join(filt),
                    "-map", "[v]", "-ar", "48000", str(vo)], check=True)

    log = json.loads((take / "log.json").read_text())
    T = {s["step"]: s["t"] for s in log["steps"]}
    frames, ft = log["frames"], [f["t"] for f in log["frames"]]
    fw, fh = Image.open(take / "frames" / frames[0]["file"]).size

    def frame_at(x):
        lo, hi = 0, len(ft) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            lo, hi = (mid, hi) if ft[mid] <= x else (lo, mid - 1)
        return take / "frames" / frames[lo]["file"]

    # scene ranges on the new timeline
    sc_rng = {}
    for a, b, _t, sc, src in LINES:
        s0, s1 = m(a, src), m(b, src)
        lo, hi = sc_rng.get(sc, (s0, s1))
        sc_rng[sc] = (min(lo, s0), max(hi, s1))
    order = ["A", "A2", "B", "C", "D", "E", "E2", "F", "G", "H", "I"]
    bounds, cur = {}, 0.0
    for i, sc in enumerate(order):
        end = sc_rng[order[i + 1]][0] - 0.05 if i + 1 < len(order) else total_voice + 0.3
        bounds[sc] = (cur, end)
        cur = end

    cards = take / "cards"
    cards.mkdir(exist_ok=True)
    card(cards / "intro.jpg", ["CaseNote"], "An on-device AI immigration assistant for international students")
    card(cards / "end.jpg", ["CaseNote"], "PrismML Bonsai 9B + Argmax  |  everything on-device  |  zero bytes uploaded")
    pk = cards / "packet.jpg"
    bg = Image.new("RGB", (W, H), NAVY)
    thumb = next(take.glob("packet.pdf.png"), None)
    if thumb:
        pg = Image.open(thumb).convert("RGB")
        pg.thumbnail((W - 200, H - 220))
        bg.paste(pg, ((W - pg.width) // 2, 50))
    bg.save(pk, quality=95)
    for c in (cards / "intro.jpg", cards / "end.jpg", pk):
        Image.open(c).convert("RGB").resize((fw, fh), Image.LANCZOS).save(c, quality=95)

    load_mid = (T["docs_start"] + T["findings"]) / 2
    clips = {
        "A": (T["docs_start"] - 1.0, load_mid, "Everything runs on this Mac."),
        "A2": (load_mid, T["findings"] + 0.8, "Apple Vision OCR  +  MRZ check digits  +  Bonsai 9B"),
        "B": (T["previews"], T["previews_end"], "Every field shows where it came from: MRZ, OCR or Bonsai"),
        "C": (T["previews_end"], T["sheet_close"], "7 official DHS, ICE and CBP rules, each one cited"),
        "D": (T["path"], T["path_end"] + 0.8, "Dates computed from your own I-20, each stage cited"),
        "E": (T["rec_start"] - 0.6, T["answer"] + 0.8, "Argmax WhisperKit  >  Bonsai 9B  >  Argmax TTSKit"),
        "F": (T["deadlines"], T["meeting_start"], "Deadlines, exported to Apple Calendar"),
        "G": (T["meeting_start"], T["packet_start"], "Argmax SpeakerKit separates the speakers"),
    }

    # zoom rectangle around the chat panel, at the frame's aspect ratio
    cb = log["chat_box"]
    mx = 60
    x0, y0 = max(0, cb["x"] - mx), max(0, cb["y"] - mx)
    x1, y1 = min(fw, cb["x"] + cb["width"] + mx), min(fh, cb["y"] + cb["height"] + mx)  # visible part only
    ar = fw / fh
    w, h = x1 - x0, y1 - y0
    if w / h < ar:
        w = h * ar
    else:
        h = w / ar
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    zx0, zy0 = min(max(0, cx - w / 2), fw - w), min(max(0, cy - h / 2), fh - h)
    zoom_dir = take / "zoom"
    zoom_dir.mkdir(exist_ok=True)

    concat, overlays = [], []
    for sc in order:
        s0, s1 = bounds[sc]
        D = s1 - s0
        n = max(1, round(D * FPS))
        if sc == "A":
            nt = round(TITLE * FPS)
            concat.append((cards / "intro.jpg", nt))
            a, b, cap = clips["A"]
            rest = n - nt
            for i in range(rest):
                concat.append((frame_at(a + (b - a) * i / rest), 1))
            sp = (b - a) / (rest / FPS)
            if sp > 1.25:
                overlays.append(("speed", s0 + TITLE, s1, f"Sped up {sp:.1f}x" if sp < 2 else f"Sped up {sp:.0f}x"))
            overlays.append(("cap", s0 + TITLE + 0.2, s1 - 0.1, cap))
        elif sc == "E2":
            a, b = T["answer"], T["answer_end"]
            for i in range(n):
                tt = i / FPS
                z = ease(tt / 1.2) * (1 - ease((tt - (D - 1.2)) / 1.2))  # in, hold, out
                src = Image.open(frame_at(a + (b - a) * i / n))
                bx0, by0 = zx0 * z, zy0 * z
                bw, bh = fw + (w - fw) * z, fh + (h - fh) * z
                im = src.crop((round(bx0), round(by0), round(bx0 + bw), round(by0 + bh))).resize((fw, fh), Image.LANCZOS)
                p = zoom_dir / f"z{i:04d}.jpg"
                im.save(p, quality=88)
                concat.append((p, 1))
            overlays.append(("cap", s0 + 0.2, s1 - 0.1, "The AI lawyer answers out loud, generated on-device by Argmax TTSKit"))
        elif sc == "H":
            concat.append((pk, n))
            overlays.append(("cap", s0 + 0.1, s1 - 0.1, "One click: an English case packet for the attorney"))
        elif sc == "I":
            concat.append((cards / "end.jpg", n))
        else:
            a, b, cap = clips[sc]
            for i in range(n):
                concat.append((frame_at(a + (b - a) * i / n), 1))
            sp = (b - a) / D
            if sp > 1.25:
                overlays.append(("speed", s0, s1, f"Sped up {sp:.1f}x" if sp < 2 else f"Sped up {sp:.0f}x"))
            overlays.append(("cap", s0 + 0.2, s1 - 0.1, cap))
    total = sum(c for _, c in concat) / FPS

    lst = take / "frames_v2.txt"
    with lst.open("w") as f:
        prev, kk = None, 0
        for path, c in concat + [(None, 0)]:
            if path == prev:
                kk += c
                continue
            if prev is not None:
                f.write(f"file '{prev}'\nduration {kk / FPS:.5f}\n")
            prev, kk = path, c
        f.write(f"file '{concat[-1][0]}'\n")

    # subtitles
    subs = [(m(l[0], l[4]), m(l[1], l[4]), l[2], l[4]) for l in LINES]
    subs = [(a, min(b + 0.15, subs[i + 1][0] - 0.03) if i + 1 < len(subs) else b + 0.15, t, s) for i, (a, b, t, s) in enumerate(subs)]

    def ts(x):
        h_, r = divmod(x, 3600)
        mi, s = divmod(r, 60)
        return f"{int(h_):02d}:{int(mi):02d}:{s:06.3f}".replace(".", ",")
    (take / "CaseNote_demo_v2.srt").write_text("\n".join(
        f"{i + 1}\n{ts(a)} --> {ts(b)}\n{('AI lawyer: ' if s == 1 else '') + t}\n" for i, (a, b, t, s) in enumerate(subs)))

    def font(size, weight):
        f = ImageFont.truetype(SF, size)
        try:
            f.set_variation_by_name(weight)
        except Exception:
            pass
        return f

    def wrap(text, f, maxw):
        out, line = [], ""
        for word in text.split():
            test = (line + " " + word).strip()
            if f.getlength(test) <= maxw:
                line = test
            else:
                out.append(line)
                line = word
        return out + [line]

    labels = take / "labels_v2"
    labels.mkdir(exist_ok=True)
    pngs = []
    for i, (a, b, text, s) in enumerate(subs):
        f = font(44, "Medium")
        ls = wrap(text, f, 1500)
        bw = int(max(f.getlength(l) for l in ls)) + 56 + (150 if s == 1 else 0)
        bh = 58 * len(ls) + 28
        img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        fill = (0, 94, 162, 225) if s == 1 else (22, 46, 81, 215)  # AI lawyer lines in government blue
        d.rounded_rectangle([0, 0, bw - 1, bh - 1], radius=14, fill=fill)
        x_off = 0
        if s == 1:
            tag = font(30, "Semibold")
            d.text((26, 22), "AI lawyer", font=tag, fill=(200, 225, 245))
            x_off = 75
        for j, l in enumerate(ls):
            d.text(((bw - f.getlength(l)) / 2 + x_off, 12 + j * 58), l, font=f, fill=WHITE)
        p = labels / f"sub{i:02d}.png"
        img.save(p)
        pngs.append((p, (W - bw) // 2, H - bh - 46, a, b))
    for i, (kind, a, b, text) in enumerate(overlays):
        f = font(32 if kind == "speed" else 34, "Semibold")
        bb = f.getbbox(text)
        bw, bh = bb[2] - bb[0] + 40, 60
        img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, bw - 1, bh - 1], radius=12, fill=(22, 46, 81, 225))
        d.text((20 - bb[0], 11), text, font=f, fill=WHITE)
        p = labels / f"lab{i:02d}.png"
        img.save(p)
        pngs.append((p, W - bw - 40 if kind == "speed" else 40, 36, a, b))

    cuts = sorted({0.0, total} | {round(x, 3) for *_, a, b in pngs for x in (a, b)})
    cuts = [c for c in cuts if 0 <= c <= total]
    ol = take / "overlay_v2.txt"
    cache, active = {}, ()
    with ol.open("w") as f:
        for i in range(len(cuts) - 1):
            t0, t1 = cuts[i], cuts[i + 1]
            if t1 - t0 < 1 / FPS:
                continue
            mid = (t0 + t1) / 2
            active = tuple(j for j, (*_, a, b) in enumerate(pngs) if a <= mid < b)
            if active not in cache:
                fr = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                for j in active:
                    p, x, y, _, _ = pngs[j]
                    fr.alpha_composite(Image.open(p), (int(x), int(y)))
                fp = labels / f"state{len(cache):03d}.png"
                fr.save(fp)
                cache[active] = fp
            f.write(f"file '{cache[active]}'\nduration {t1 - t0:.4f}\n")
        f.write(f"file '{cache[active]}'\n")

    out = take / "CaseNote_demo_v2.mp4"
    fc = f"[0:v]scale={W}:{H}:flags=lanczos,fps={FPS}[base];[2:v]fps={FPS},format=rgba[ov];[base][ov]overlay=0:0:format=auto[vout]"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(vo),
                    "-f", "concat", "-safe", "0", "-i", str(ol), "-filter_complex", fc, "-map", "[vout]", "-map", "1:a",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "192k",
                    "-t", f"{total:.2f}", "-movflags", "+faststart", str(out)], check=True)
    print(f"tempo {tempo:.3f}, video {dur(out):.1f}s")
    for sc in order:
        print(sc, f"{bounds[sc][0]:.1f}-{bounds[sc][1]:.1f}")


if __name__ == "__main__":
    main(ROOT / sys.argv[1])
