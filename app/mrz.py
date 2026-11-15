"""Machine Readable Zone (MRZ) helpers for passports (TD3) and visas (MRV-A).

Both formats are two lines of 44 characters defined by ICAO Doc 9303.
Parsing is deterministic: no AI is involved, and check digits are verified.
"""

from __future__ import annotations

import re
from datetime import date

WEIGHTS = (7, 3, 1)


def _char_value(c: str) -> int:
    if c.isdigit():
        return int(c)
    if "A" <= c <= "Z":
        return ord(c) - ord("A") + 10
    return 0  # '<' filler


def check_digit(field: str) -> str:
    total = sum(_char_value(c) * WEIGHTS[i % 3] for i, c in enumerate(field))
    return str(total % 10)


def _pad(s: str, n: int) -> str:
    return (s + "<" * n)[:n]


def _name_field(surname: str, given: str, n: int) -> str:
    sur = re.sub(r"[^A-Z]", "<", surname.upper())
    giv = re.sub(r"[^A-Z]", "<", given.upper())
    return _pad(f"{sur}<<{giv}", n)


def _yymmdd(d: date) -> str:
    return d.strftime("%y%m%d")


def build_td3(surname, given, number, nationality, dob: date, sex, expiry: date, issuer=None) -> tuple[str, str]:
    issuer = issuer or nationality
    line1 = _pad("P<" + issuer, 5) + _name_field(surname, given, 39)
    num = _pad(number, 9)
    personal = _pad("", 14)
    parts = [
        num + check_digit(num),
        nationality,
        _yymmdd(dob) + check_digit(_yymmdd(dob)),
        sex,
        _yymmdd(expiry) + check_digit(_yymmdd(expiry)),
        personal + check_digit(personal),
    ]
    body = "".join(parts)
    composite = body[0:10] + body[13:20] + body[21:43]
    line2 = body + check_digit(composite)
    return line1, line2


def build_mrva(surname, given, number, nationality, dob: date, sex, expiry: date, optional="") -> tuple[str, str]:
    line1 = "V<USA" + _name_field(surname, given, 39)
    num = _pad(number, 9)
    line2 = (
        num + check_digit(num) + nationality
        + _yymmdd(dob) + check_digit(_yymmdd(dob)) + sex
        + _yymmdd(expiry) + check_digit(_yymmdd(expiry))
        + _pad(optional, 16)
    )
    return line1, line2


def _parse_date(yymmdd: str, future: bool) -> date | None:
    try:
        yy, mm, dd = int(yymmdd[0:2]), int(yymmdd[2:4]), int(yymmdd[4:6])
    except ValueError:
        return None
    this_year = date.today().year % 100
    if future:
        century = 2000
    else:
        century = 1900 if yy > this_year else 2000
    try:
        return date(century + yy, mm, dd)
    except ValueError:
        return None


_FIX = str.maketrans({"O": "0", "o": "0", " ": ""})


def find_mrz(lines: list[str]) -> tuple[str, str] | None:
    """Find two consecutive MRZ lines in OCR output (tolerates small OCR noise)."""
    norm = []
    for raw in lines:
        s = raw.replace(" ", "").upper()
        for ch in "«‹〈<":
            s = s.replace(ch, "<")
        s = s.replace("Ø", "0")
        norm.append(re.sub(r"[^A-Z0-9<]", "", s))
    for i in range(len(norm) - 1):
        a, b = norm[i], norm[i + 1]
        # Line 1 often loses trailing fillers in OCR, so only require the header.
        if re.match(r"^[PV]<[A-Z]{3}[A-Z<]+<<", a) and len(b) >= 40 and re.search(r"\d{6}", b):
            return _pad(a, 44), _pad(b, 44)
    return None


def parse(line1: str, line2: str) -> dict:
    """Parse TD3 or MRV-A lines into fields, with check-digit validation."""
    kind = "passport" if line1.startswith("P") else "visa"
    issuer = line1[2:5].replace("<", "")
    names = line1[5:].split("<<", 1)
    surname = names[0].replace("<", " ").strip()
    given = names[1].replace("<", " ").strip() if len(names) > 1 else ""
    # Digits-only positions: normalise common OCR confusions there.
    num = line2[0:9]
    dob_s = line2[13:19].translate(_FIX)
    exp_s = line2[21:27].translate(_FIX)
    checks = {
        "number": check_digit(num) == line2[9],
        "dob": check_digit(dob_s) == line2[19],
        "expiry": check_digit(exp_s) == line2[27],
    }
    out = {
        "doc_kind": kind,
        "issuer": issuer,
        "surname": surname,
        "given_names": given,
        "number": num.replace("<", ""),
        "nationality": line2[10:13].replace("<", ""),
        "dob": _parse_date(dob_s, future=False),
        "sex": line2[20],
        "expiry": _parse_date(exp_s, future=True),
        "optional": line2[28:44].replace("<", " ").strip(),
        "checks_ok": all(checks.values()),
        "checks": checks,
        "raw": [line1, line2],
    }
    return out
