"""Turn OCR lines into typed document fields.

Order of trust:
  1. MRZ (passport / visa): deterministic parse with check digits.
  2. Bonsai reads the OCR text and returns JSON fields (the "AI read").
  3. Every Bonsai field is validated against the label/value pairs found by
     geometry; if Bonsai's value is missing or malformed we fall back.
Each field records where it came from and its box on the page, so the UI can
highlight the exact spot a problem was found.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from . import llm, mrz

DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def group_rows(lines: list[dict]) -> list[dict]:
    """Group OCR lines that sit on the same visual row."""
    rows: list[dict] = []
    for ln in sorted(lines, key=lambda l: l["box"][1] + l["box"][3] / 2):
        cy = ln["box"][1] + ln["box"][3] / 2
        for r in rows:
            if abs(r["cy"] - cy) < max(r["h"], ln["box"][3]) * 0.6:
                r["items"].append(ln)
                break
        else:
            rows.append({"cy": cy, "h": ln["box"][3], "items": [ln]})
    for r in rows:
        r["items"].sort(key=lambda l: l["box"][0])
        r["text"] = " ".join(i["text"] for i in r["items"])
    return rows


def label_values(rows: list[dict]) -> dict[str, dict]:
    """Map a normalised label to {value, box} using 'Label:' followed by text on the same row."""
    out = {}
    for r in rows:
        items = r["items"]
        for i, it in enumerate(items):
            t = it["text"].strip()
            if t.endswith(":") and i + 1 < len(items):
                v = items[i + 1]
                out[norm_label(t)] = {"value": v["text"].strip(), "box": v["box"]}
            elif ":" in t and not t.endswith(":"):
                k, _, v = t.partition(":")
                if v.strip():
                    out[norm_label(k)] = {"value": v.strip(), "box": it["box"]}
    return out


def norm_label(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    s = s.replace("O", "0").replace("Ø", "0")
    m = DATE_RE.search(s)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None
    try:
        return datetime.fromisoformat(s.strip()[:10]).date()
    except ValueError:
        return None


def classify(text: str) -> str:
    t = text.upper()
    if "I-94" in t or "ADMIT UNTIL" in t:
        return "i94"
    if "I-20" in t or "SEVIS ID" in t or "TRAVEL ENDORSEMENT" in t:
        return "i20"
    if "NONIMMIGRANT VISA" in t or "\nV<USA" in t or "V<USA" in t:
        return "visa"
    if "PASSPORT" in t or "P<" in t:
        return "passport"
    return "unknown"


def _mrz_rows(rows):
    texts = []
    for r in rows:
        s = r["text"].replace(" ", "").replace("Ø", "0").replace("«", "<").upper()
        texts.append(s)
    return texts


# Fields we want per document type: name -> (labels to look for, kind)
SCHEMA = {
    "passport": {
        "surname": (["surname"], "name"), "given_names": (["given names", "given name"], "name"),
        "number": (["passport no"], "id"), "dob": (["date of birth"], "date"),
        "expiry": (["date of expiry"], "date"), "nationality": (["nationality"], "text"),
    },
    "visa": {
        "surname": (["surname"], "name"), "given_names": (["given name"], "name"),
        "passport_number": (["passport number"], "id"), "visa_class": (["visa type class"], "text"),
        "expiry": (["expiration date"], "date"), "annotation": (["annotation"], "text"),
    },
    "i20": {
        "sevis_id": (["sevis id"], "id"), "surname": (["surname primary name"], "name"),
        "given_names": (["given name"], "name"), "dob": (["date of birth"], "date"),
        "school": (["school name"], "text"), "program_start": (["program start date"], "date"),
        "program_end": (["program end date"], "date"), "travel_signature_date": (["travel signature date"], "date"),
    },
    "i94": {
        "record_number": (["admission i 94 record number"], "id"), "entry_date": (["most recent date of entry"], "date"),
        "class_of_admission": (["class of admission"], "text"), "admit_until": (["admit until date"], "text"),
        "surname": (["last surname"], "name"), "given_names": (["first given name"], "name"),
        "dob": (["birth date"], "date"), "passport_number": (["document number"], "id"),
    },
}


def _valid(kind: str, v) -> bool:
    if v in (None, ""):
        return False
    if kind == "date":
        return parse_date(str(v)) is not None
    if kind == "name":
        return bool(re.fullmatch(r"[A-Z][A-Z \-']*", str(v).upper().strip()))
    return True


_WM = set("SPECIMN")


def is_watermark(text: str) -> bool:
    """Drop OCR fragments of the diagonal SPECIMEN watermark (e.g. 'EN', 'SPECI', 'F CIMEN')."""
    t = text.strip().upper()
    letters = t.replace(" ", "")
    if not (2 <= len(letters) <= 8) or not re.fullmatch(r"[A-Z ]+", t):
        return False
    return sum(c in _WM for c in letters) / len(letters) >= 0.75


def extract(lines: list[dict], use_llm: bool = True) -> dict:
    lines = [l for l in lines if not is_watermark(l["text"])]
    rows = group_rows(lines)
    full_text = "\n".join(r["text"] for r in rows)
    doc_type = classify(full_text)
    lv = label_values(rows)
    fields: dict[str, dict] = {}
    schema = SCHEMA.get(doc_type, {})

    # 1) geometry-based label/value pairs
    geo = {}
    for name, (labels, kind) in schema.items():
        for lab in labels:
            if lab in lv:
                geo[name] = lv[lab]
                break

    # 2) Bonsai reads the text. Passport/visa with a valid MRZ don't need it:
    #    deterministic beats probabilistic, and it frees Bonsai for the I-20 / I-94.
    ai = {}
    m_pre = mrz.find_mrz(_mrz_rows(rows)) if doc_type in ("passport", "visa") else None
    if m_pre and mrz.parse(m_pre[0], m_pre[1])["checks_ok"]:
        use_llm = False
    if use_llm and schema:
        ai = llm.extract_fields(doc_type, full_text, list(schema.keys())) or {}

    for name, (labels, kind) in schema.items():
        a = ai.get(name)
        g = geo.get(name)
        if _valid(kind, a):
            val, src = str(a).strip(), "bonsai"
            # agreement check with geometry, if both exist
            if g and kind == "date" and parse_date(g["value"]) != parse_date(val):
                val, src = g["value"], "ocr"  # trust the printed value
        elif g and _valid(kind, g["value"]):
            val, src = g["value"], "ocr"
        else:
            continue
        box = g["box"] if g else None
        fields[name] = {"value": parse_date(val).isoformat() if kind == "date" else val.upper() if kind == "name" else val,
                        "source": src, "box": box}

    # 3) MRZ overrides for passport/visa (most reliable)
    m = mrz.find_mrz(_mrz_rows(rows))
    mrz_info = None
    if m:
        l1 = m[0][:5] + m[0][5:].replace("0", "O")  # names never contain digits
        info = mrz.parse(l1, m[1])
        mrz_info = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in info.items()}
        mrz_box = next((r["items"][0]["box"] for r in rows if r["text"].replace(" ", "").upper().startswith(("P<", "V<"))), None)
        for k_src, k_dst in (("surname", "surname"), ("given_names", "given_names"), ("dob", "dob"), ("expiry", "expiry")):
            v = mrz_info.get(k_src)
            if v and (k_dst in fields or doc_type in ("passport", "visa")):
                if k_dst not in fields or info["checks_ok"]:
                    fields[k_dst] = {"value": v, "source": "mrz", "box": fields.get(k_dst, {}).get("box") or mrz_box}
        if doc_type == "passport" and info["checks"]["number"]:
            fields["number"] = {"value": mrz_info["number"], "source": "mrz", "box": fields.get("number", {}).get("box")}
        if doc_type == "passport" and mrz_info.get("nationality"):
            fields["nationality"] = {"value": mrz_info["nationality"], "source": "mrz", "box": fields.get("nationality", {}).get("box") or mrz_box}

    return {"type": doc_type, "fields": fields, "mrz": mrz_info, "text": full_text}
