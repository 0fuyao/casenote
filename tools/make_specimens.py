"""Generate four SPECIMEN demo documents with fictional data.

These are deliberately simplified mock-ups (not replicas of official layouts),
watermarked on every page, for demoing CaseNote. The person, school and numbers
are invented. Two problems are planted on purpose:
  1. The I-20 travel endorsement is 14 months old (limit: one year).
  2. The I-94 has the surname and given name swapped versus the passport.
"""

from datetime import date
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.mrz import build_mrva, build_td3  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "samples"
OUT.mkdir(exist_ok=True)

SUP = "/System/Library/Fonts/Supplemental/"
F = lambda size, bold=False: ImageFont.truetype(SUP + ("Arial Bold.ttf" if bold else "Arial.ttf"), size)
MONO = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 30)

P = dict(surname="ZHANG", given="XIAOYU", dob=date(2006, 3, 14), sex="F", nat="CHN")
PASSPORT_NO = "EK8812345"
SEVIS = "N0034567890"
SCHOOL = "LAKEVIEW UNIVERSITY"


def canvas(w, h, title, tint):
    img = Image.new("RGB", (w, h), tint)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, 56], fill=(61, 74, 92))
    d.text((24, 14), "SPECIMEN  -  FICTIONAL DATA  -  NOT A REAL DOCUMENT  -  CaseNote demo", font=F(24, True), fill="white")
    d.text((40, 80), title, font=F(34, True), fill=(20, 20, 20))
    return img, d


def watermark(img):
    w, h = img.size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.text((w * 0.12, h * 0.38), "SPECIMEN", font=F(int(h * 0.22), True), fill=(70, 90, 120, 24))
    layer = layer.rotate(18, center=(w / 2, h / 2))
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def rows(d, x, y, items, gap=46, size=26):
    for label, value in items:
        d.text((x, y), f"{label}:", font=F(size), fill=(90, 90, 90))
        d.text((x + 470, y), value, font=F(size, True), fill=(15, 15, 15))
        y += gap
    return y


def fmt(dt: date) -> str:
    return dt.strftime("%m/%d/%Y")


def passport():
    img, d = canvas(1400, 900, "PASSPORT  (data page)", (238, 242, 236))
    d.rectangle([40, 140, 300, 480], outline=(120, 120, 120), width=3)
    d.text((95, 290), "PHOTO", font=F(36, True), fill=(150, 150, 150))
    exp = date(2031, 6, 30)
    rows(d, 340, 150, [
        ("Type / Country code", "P / CHN"),
        ("Passport No.", PASSPORT_NO),
        ("Surname", P["surname"]),
        ("Given names", P["given"]),
        ("Nationality", "CHINESE"),
        ("Date of birth", fmt(P["dob"])),
        ("Sex", P["sex"]),
        ("Date of expiry", fmt(exp)),
    ])
    l1, l2 = build_td3(P["surname"], P["given"], PASSPORT_NO, P["nat"], P["dob"], P["sex"], exp)
    d.rectangle([0, 740, 1400, 900], fill=(250, 250, 248))
    d.text((40, 762), l1, font=MONO, fill="black")
    d.text((40, 818), l2, font=MONO, fill="black")
    watermark(img).save(OUT / "1_passport.png")


def visa():
    img, d = canvas(1400, 900, "U.S. NONIMMIGRANT VISA  (foil)", (236, 240, 248))
    d.rectangle([40, 140, 300, 480], outline=(120, 120, 120), width=3)
    d.text((95, 290), "PHOTO", font=F(36, True), fill=(150, 150, 150))
    exp = date(2028, 7, 1)
    rows(d, 340, 150, [
        ("Visa type / Class", "R / F-1"),
        ("Surname", P["surname"]),
        ("Given name", P["given"]),
        ("Passport number", PASSPORT_NO),
        ("Issue date", fmt(date(2025, 7, 2))),
        ("Expiration date", fmt(exp)),
        ("Entries", "M"),
        ("Annotation", f"SEVIS {SEVIS} {SCHOOL}"),
    ])
    l1, l2 = build_mrva(P["surname"], P["given"], "61234567", P["nat"], P["dob"], P["sex"], exp, optional=PASSPORT_NO)
    d.rectangle([0, 740, 1400, 900], fill=(250, 250, 252))
    d.text((40, 762), l1, font=MONO, fill="black")
    d.text((40, 818), l2, font=MONO, fill="black")
    watermark(img).save(OUT / "2_visa.png")


def i20():
    img, d = canvas(1400, 1250, "FORM I-20  Certificate of Eligibility (F-1)  -  simplified mock-up", (250, 250, 246))
    y = rows(d, 40, 150, [
        ("SEVIS ID", SEVIS),
        ("Surname / Primary name", P["surname"]),
        ("Given name", P["given"]),
        ("Date of birth", fmt(P["dob"])),
        ("Country of citizenship", "CHINA"),
        ("Class of admission", "F-1"),
        ("School name", SCHOOL),
        ("Education level", "BACHELOR'S"),
        ("Major", "ELECTRICAL ENGINEERING"),
        ("Program start date", fmt(date(2025, 8, 25))),
        ("Program end date", fmt(date(2029, 5, 20))),
    ])
    d.line([40, y + 10, 1360, y + 10], fill=(60, 60, 60), width=3)
    d.text((40, y + 30), "PAGE 2  -  TRAVEL ENDORSEMENT (DSO signature for re-entry)", font=F(28, True), fill=(20, 20, 20))
    rows(d, 40, y + 90, [
        ("DSO name", "J. RIVERA (fictional)"),
        ("DSO signature", "J. Rivera"),
        ("Travel signature date", fmt(date(2025, 9, 10))),
    ])
    watermark(img).save(OUT / "3_i20.png")


def i94():
    img, d = canvas(1400, 900, "MOST RECENT I-94  (printout, simplified mock-up)", (246, 246, 246))
    rows(d, 40, 160, [
        ("Admission (I-94) Record Number", "123456789A1"),
        ("Most Recent Date of Entry", fmt(date(2025, 8, 20))),
        ("Class of Admission", "F1"),
        ("Admit Until Date", "D/S"),
        # Planted problem: names swapped relative to the passport.
        ("Last/Surname", P["given"]),
        ("First (Given) Name", P["surname"]),
        ("Birth Date", fmt(P["dob"])),
        ("Document Number", PASSPORT_NO),
        ("Country of Citizenship", "CHINA"),
    ], gap=54)
    watermark(img).save(OUT / "4_i94.png")


if __name__ == "__main__":
    passport(); visa(); i20(); i94()
    print("wrote", sorted(p.name for p in OUT.glob("*.png")))
