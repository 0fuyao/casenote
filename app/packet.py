"""English case packet (PDF) for a licensed attorney, built locally with ReportLab."""

from __future__ import annotations

import re
from datetime import date
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))  # built-in CJK font for Chinese Q&A

LABELS = [
    ("surname", "Surname"), ("given_names", "Given names"), ("dob", "Date of birth"),
    ("nationality", "Nationality"), ("passport_number", "Passport no."), ("passport_expiry", "Passport expiry"),
    ("visa_class", "Visa class"), ("visa_expiry", "Visa expiry"), ("sevis_id", "SEVIS ID"), ("school", "School"),
    ("program_start", "Program start"), ("program_end", "Program end"),
    ("travel_signature_date", "I-20 travel signature"), ("i94_class", "I-94 class"),
    ("i94_admit_until", "I-94 admit until"), ("i94_entry_date", "Most recent entry"),
]


def build(profile: dict, issues: list[dict], qa: list[dict], summary: str, return_date: date, consult: dict | None = None) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, leftMargin=0.8 * inch, rightMargin=0.8 * inch,
                            topMargin=0.7 * inch, bottomMargin=0.7 * inch, title="CaseNote case packet")
    ss = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=ss["Heading2"], spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9.5, leading=13)
    cjk = ParagraphStyle("c", parent=body, fontName="STSong-Light")
    small = ParagraphStyle("s", parent=body, fontSize=8, textColor=colors.grey)

    el = [Paragraph("CaseNote — Client Case Packet for Attorney Review", ss["Title"]),
          Paragraph(f"Prepared on-device on {date.today().isoformat()} · Planned re-entry {return_date.isoformat()} · "
                    "Generated from client-uploaded documents; verify against originals.", small),
          Spacer(1, 8)]

    el.append(Paragraph("Intake summary (AI draft by Bonsai 9B; verify against the issues table)", h))
    for line in [l.strip().lstrip("-•*0123456789. ").strip() for l in summary.splitlines() if l.strip()]:
        el.append(Paragraph("• " + line, body))

    el.append(Paragraph("Flagged issues", h))
    if issues:
        data = [["Sev.", "Issue", "Detail", "Source"]]
        for i in issues:
            data.append([i["severity"].upper(), Paragraph(i["title_en"], body),
                         Paragraph(f'{i["detail_en"]}<br/><i>Suggested next step:</i> {i.get("action_en", "")}', body),
                         Paragraph(f'<link href="{i["url"]}">{i["source"]}</link>', body)])
        t = Table(data, colWidths=[0.55 * inch, 1.5 * inch, 2.6 * inch, 2.2 * inch], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
                               ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbbbbb")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"), ("FONTSIZE", (0, 0), (-1, -1), 8.5)]))
        el.append(t)
    else:
        el.append(Paragraph("No issues flagged by the rule checks.", body))

    el.append(Paragraph("Client profile (from documents)", h))
    rows = [[k2, str(profile.get(k) or "—")] for k, k2 in LABELS]
    t = Table(rows, colWidths=[2.0 * inch, 4.8 * inch])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")), ("FONTSIZE", (0, 0), (-1, -1), 8.5)]))
    el.append(t)

    if qa:
        el.append(Paragraph("Client questions (original language)", h))
        for item in qa:
            st = lambda t: cjk if re.search(r"[\u4e00-\u9fff]", t) else body
            el.append(Paragraph(f"<b>Q:</b> {item['q']}", st(item["q"])))
            el.append(Paragraph(f"<b>A (AI, information only):</b> {item['a']}".replace("\n", "<br/>"), st(item["a"])))
            el.append(Spacer(1, 4))

    if consult and consult.get("lines"):
        el.append(Paragraph("Consultation (transcribed and speaker-separated on-device by Argmax)", h))
        for line in [l.strip().lstrip("-•* ").strip() for l in (consult.get("notes") or "").splitlines() if l.strip()]:
            el.append(Paragraph("• " + line, body))
        el.append(Spacer(1, 4))
        for l in consult["lines"]:
            mm, ss_ = divmod(int(l["start"]), 60)
            st = cjk if re.search(r"[\u4e00-\u9fff]", l["text"]) else body
            el.append(Paragraph(f"<b>{l['speaker']}</b> <font color='grey'>{mm}:{ss_:02d}</font>  {l['text']}", st))

    el.append(Spacer(1, 10))
    el.append(Paragraph("This packet contains general legal information prepared by software, not legal advice. "
                        "All conclusions require review by a licensed attorney.", small))
    doc.build(el)
    return buf.getvalue()
