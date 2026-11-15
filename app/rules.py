"""Deterministic F-1 re-entry checks. Every rule cites an official page.

Sources were opened and checked on 2026-11-15. A rule with no official
source is not included (better fewer rules than a wrong one).
"""

from __future__ import annotations

from datetime import date, timedelta

RULES = [
    {
        "id": "R1",
        "zh": "F-1 学生重新入境时，I-20 第二页的 DSO 旅行签字有效期为一年（以计划返回美国的日期计算）。",
        "en": "For F-1 students, the DSO travel endorsement on the I-20 is valid for one year from the signature date relative to the return date.",
        "source_name": "Study in the States (DHS): DSOs and the Form I-20",
        "url": "https://studyinthestates.dhs.gov/schools/report/dsos-and-the-form-i-20",
    },
    {
        "id": "R2",
        "zh": "各份材料上的姓名、出生日期、护照号应一致；入境时 CBP 在 I-94 上的错误（如个人信息不准确）可到 CBP 延期检查办公室（Deferred Inspection）更正。",
        "en": "Names, birth date and passport number should agree across documents; CBP Deferred Inspection sites correct entry-time I-94 errors such as inaccurate biographical information.",
        "source_name": "CBP: Deferred Inspection Sites",
        "url": "https://www.cbp.gov/contact/ports/deferred-inspection-sites",
    },
    {
        "id": "R3",
        "zh": "F-1 学生的 I-94 入境类别应为 F-1。2026 年 9 月 15 日新规生效后，新入境者的 I-94 写的是固定的「停留截止日」（Admit Until Date），之前入境的旧 I-94 可能仍写 D/S。",
        "en": "An F-1 student's I-94 should show class F-1. Under the final rule effective Sept 15, 2026, new admissions get a fixed Admit Until Date instead of D/S; older I-94s may still show D/S.",
        "source_name": "Study in the States (DHS): Elimination of Duration of Status FAQ",
        "url": "https://studyinthestates.dhs.gov/elimination-of-duration-of-status-frequently-asked-questions",
    },
    {
        "id": "R4",
        "zh": "F-1 签证可以在美国境内过期，但出境后重新入境一般需要有效的 F-1 签证（例外：去加拿大、墨西哥或邻近岛屿不超过 30 天的自动签证重新生效）。",
        "en": "Re-entry generally requires a valid, current F-1 visa (exception: automatic revalidation after trips of fewer than 30 days to Canada, Mexico or adjacent islands).",
        "source_name": "ICE SEVP: Travel",
        "url": "https://www.ice.gov/sevis/travel",
    },
    {
        "id": "R5",
        "zh": "重新入境时护照应在入境日后至少还有 6 个月有效期；中国（PRC）不在 CBP「六个月俱乐部」豁免名单中（名单日期 2024-01-28）。",
        "en": "The passport should be valid at least six months after the re-entry date; China (PRC) is not on CBP's Six-Month Club exemption list (list effective Jan 28, 2024).",
        "source_name": "ICE SEVP: Travel; CBP Six-Month Club list",
        "url": "https://www.ice.gov/sevis/travel",
    },
    {
        "id": "R6",
        "zh": "完成 I-20 上的项目后，F-1 学生有 60 天宽限期离境、转学或转换身份（新规下按固定停留期入境者为 30 天）。",
        "en": "After the I-20 program end date, F students have 60 days to depart, transfer or change status (30 days for those admitted under the new fixed-period rule).",
        "source_name": "Study in the States (DHS): Maintaining Status",
        "url": "https://studyinthestates.dhs.gov/students/maintaining-status",
    },
    {
        "id": "R7",
        "zh": "毕业后 OPT：I-765 最早可在项目结束前 90 天递交，最晚在结束后 60 天内，且须在 DSO 于 SEVIS 推荐后 30 天内递交。",
        "en": "Post-completion OPT: file Form I-765 up to 90 days before and no later than 60 days after the program end date, within 30 days of the DSO recommendation in SEVIS.",
        "source_name": "Study in the States (DHS): Applying for Practical Training",
        "url": "https://studyinthestates.dhs.gov/students/work/applying-for-practical-training",
    },
]
RULES_BY_ID = {r["id"]: r for r in RULES}


def _d(v):
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        return None


def _f(docs, kind, field):
    """Return (value, doc_id, box) of a field from the first doc of that kind."""
    for doc_id, doc in docs.items():
        if doc["type"] == kind and field in doc["fields"]:
            f = doc["fields"][field]
            return f["value"], doc_id, f.get("box")
    return None, None, None


def build_profile(docs: dict) -> dict:
    def g(kind, field):
        return _f(docs, kind, field)[0]
    return {
        "surname": g("passport", "surname") or g("i20", "surname"),
        "given_names": g("passport", "given_names") or g("i20", "given_names"),
        "dob": g("passport", "dob") or g("i20", "dob"),
        "nationality": g("passport", "nationality"),
        "passport_number": g("passport", "number"),
        "passport_expiry": g("passport", "expiry"),
        "visa_class": g("visa", "visa_class"),
        "visa_expiry": g("visa", "expiry"),
        "sevis_id": g("i20", "sevis_id"),
        "school": g("i20", "school"),
        "major": g("i20", "major"),
        "program_start": g("i20", "program_start"),
        "program_end": g("i20", "program_end"),
        "travel_signature_date": g("i20", "travel_signature_date"),
        "i94_class": g("i94", "class_of_admission"),
        "i94_admit_until": g("i94", "admit_until"),
        "i94_entry_date": g("i94", "entry_date"),
        "documents": sorted({d["type"] for d in docs.values()}),
    }


ACTIONS = {
    "R1": ("出发前联系学校 DSO 重新做旅行签字；如果已经在路上，落地后尽快联系 DSO，并把情况交给律师审核。",
           "Ask the DSO for a new travel endorsement before departure; if already travelling, contact the DSO on arrival and have an attorney review."),
    "R2": ("记下差异，入境后到 CBP 延期检查办公室（Deferred Inspection）申请更正 I-94 上的个人信息。",
           "Note the discrepancy and ask a CBP Deferred Inspection site to correct the I-94 biographical data after entry."),
    "R3": ("请 DSO 或律师确认 I-94 记录，必要时到 CBP 延期检查办公室更正。", "Have the DSO or an attorney review the I-94; correct at CBP Deferred Inspection if needed."),
    "R4": ("出发前预约续签 F-1 签证。", "Renew the F-1 visa before travelling."),
    "R5": ("出发前续办护照。", "Renew the passport before travelling."),
    "R6": ("立即联系 DSO 确认宽限期和下一步（OPT、转学或离境）。", "Contact the DSO now about the grace period and next steps."),
    "R7": ("和 DSO 约时间做 OPT 推荐，然后在窗口内递交 I-765。", "Request the DSO's OPT recommendation, then file I-765 within the window."),
}


def _issue(rule, severity, title_zh, title_en, detail_zh, detail_en, marks):
    return {"rule": rule, "action_zh": ACTIONS[rule][0], "action_en": ACTIONS[rule][1], "severity": severity, "title_zh": title_zh, "title_en": title_en,
            "detail_zh": detail_zh, "detail_en": detail_en,
            "marks": [m for m in marks if m[0]],  # (doc_id, box)
            "source": RULES_BY_ID[rule]["source_name"], "url": RULES_BY_ID[rule]["url"]}


def _norm(s):
    return " ".join((s or "").upper().split())


def check(docs: dict, return_date: date, today: date | None = None) -> list[dict]:
    today = today or date.today()
    issues = []

    # R1 travel signature
    sig, sid, sbox = _f(docs, "i20", "travel_signature_date")
    sig_d = _d(sig)
    if sig_d:
        limit = sig_d.replace(year=sig_d.year + 1)
        if return_date > limit:
            months = (return_date.year - sig_d.year) * 12 + return_date.month - sig_d.month
            issues.append(_issue("R1", "high",
                "I-20 旅行签字已过期", "I-20 travel signature expired",
                f"签字日期 {sig}，到计划入境日 {return_date.isoformat()} 已约 {months} 个月，超过一年有效期。",
                f"Travel signature signed on {sig}; it stopped being valid on {limit.isoformat()}, before the planned return date {return_date.isoformat()} (valid for one year).",
                [(sid, sbox)]))

    # R2 identity consistency across documents
    p_sur, pid, p_box = _f(docs, "passport", "surname")
    p_giv, _, pg_box = _f(docs, "passport", "given_names")
    p_dob, _, _ = _f(docs, "passport", "dob")
    p_num, _, _ = _f(docs, "passport", "number")
    for kind, label, lab_en in (("i94", "I-94", "I-94"), ("i20", "I-20", "I-20"), ("visa", "签证", "Visa")):
        sur, did, box = _f(docs, kind, "surname")
        giv, _, gbox = _f(docs, kind, "given_names")
        if p_sur and sur and giv and p_giv:
            if _norm(sur) == _norm(p_giv) and _norm(giv) == _norm(p_sur):
                issues.append(_issue("R2", "high" if kind == "i94" else "medium",
                    f"{label} 姓和名顺序颠倒", f"{lab_en} surname and given name are swapped",
                    f"护照：姓 {p_sur} / 名 {p_giv}；{label}：姓 {sur} / 名 {giv}。",
                    f"Passport: surname {p_sur}, given {p_giv}; {lab_en}: surname {sur}, given {giv}.",
                    [(did, box), (did, gbox), (pid, p_box)]))
            elif _norm(sur) != _norm(p_sur) or _norm(giv) != _norm(p_giv):
                issues.append(_issue("R2", "medium",
                    f"{label} 姓名与护照不一致", f"{lab_en} name differs from passport",
                    f"护照：{p_sur} {p_giv}；{label}：{sur} {giv}。",
                    f"Passport: {p_sur} {p_giv}; {lab_en}: {sur} {giv}.",
                    [(did, box), (did, gbox), (pid, p_box)]))
        dob, did2, dbox = _f(docs, kind, "dob")
        if p_dob and dob and dob != p_dob:
            issues.append(_issue("R2", "high", f"{label} 出生日期与护照不一致", f"{lab_en} birth date differs from passport",
                f"护照 {p_dob}，{label} {dob}。", f"Passport {p_dob}; {lab_en} {dob}.", [(did2, dbox)]))
        num, did3, nbox = _f(docs, kind, "passport_number")
        if p_num and num and _norm(num) != _norm(p_num):
            issues.append(_issue("R2", "medium", f"{label} 护照号与护照不一致", f"{lab_en} passport number differs",
                f"护照 {p_num}，{label} {num}（换过护照时常见）。", f"Passport {p_num}; {lab_en} {num} (common after a passport renewal).",
                [(did3, nbox)]))

    # R3 I-94 class / admit until
    cls, cid, cbox = _f(docs, "i94", "class_of_admission")
    if cls and _norm(cls).replace("-", "") != "F1":
        issues.append(_issue("R3", "high", "I-94 入境类别不是 F-1", "I-94 class is not F-1",
            f"I-94 上的类别是 {cls}。", f"I-94 shows class {cls}.", [(cid, cbox)]))
    aud, aid, abox = _f(docs, "i94", "admit_until")
    aud_d = _d(aud) if aud else None
    if aud and aud_d is None:
        from .extract import parse_date
        aud_d = parse_date(aud)
    if aud_d and aud_d < today:
        issues.append(_issue("R3", "high", "I-94 停留截止日已过", "I-94 Admit Until Date has passed",
            f"I-94 停留截止日 {aud_d.isoformat()} 早于今天。", f"Admit Until Date {aud_d.isoformat()} is before today.", [(aid, abox)]))

    # R4 visa validity at re-entry
    vexp, vid, vbox = _f(docs, "visa", "expiry")
    vexp_d = _d(vexp)
    if vexp_d and vexp_d < return_date:
        issues.append(_issue("R4", "high", "签证在入境日前已过期", "Visa expires before re-entry",
            f"签证有效期至 {vexp}，计划入境 {return_date.isoformat()}。", f"Visa valid until {vexp}; planned return {return_date.isoformat()}.",
            [(vid, vbox)]))

    # R5 passport six months after re-entry
    pexp, peid, pebox = _f(docs, "passport", "expiry")
    pexp_d = _d(pexp)
    if pexp_d and pexp_d < return_date + timedelta(days=182):
        issues.append(_issue("R5", "high", "护照有效期不足 6 个月", "Passport valid less than six months after re-entry",
            f"护照有效期至 {pexp}，计划入境 {return_date.isoformat()}。", f"Passport expires {pexp}; planned return {return_date.isoformat()}.",
            [(peid, pebox)]))

    # R6 / R7 program end date
    pend, pid2, pbox = _f(docs, "i20", "program_end")
    pend_d = _d(pend)
    if pend_d:
        if pend_d < today:
            issues.append(_issue("R6", "high", "I-20 项目已结束", "I-20 program end date has passed",
                f"项目结束于 {pend}，注意宽限期。", f"Program ended {pend}; grace period applies.", [(pid2, pbox)]))
        elif (pend_d - today).days <= 120:
            open_d = pend_d - timedelta(days=90)
            issues.append(_issue("R7", "info", "OPT 申请窗口临近", "OPT filing window approaching",
                f"项目 {pend} 结束；最早 {open_d.isoformat()} 可递交 I-765。", f"Program ends {pend}; I-765 may be filed from {open_d.isoformat()}.",
                [(pid2, pbox)]))

    order = {"high": 0, "medium": 1, "info": 2}
    issues.sort(key=lambda i: order[i["severity"]])
    return issues


def timeline(profile: dict, return_date: date, today: date | None = None) -> list[dict]:
    """Key dates derived from the documents, each tied to the rule that defines it."""
    today = today or date.today()
    out = []

    def add(d, title, rule, kind="deadline"):
        if not d:
            return
        days = (d - today).days
        state = "past" if days < 0 else "soon" if days <= 120 else "later"
        out.append({"date": d.isoformat(), "title": title, "rule": rule, "kind": kind, "days": days, "state": state})

    sig = _d(profile.get("travel_signature_date"))
    if sig:
        add(sig.replace(year=sig.year + 1), "I-20 travel signature stops being valid", "R1")
    add(_d(profile.get("visa_expiry")), "F-1 visa expires (needed to re-enter)", "R4")
    pexp = _d(profile.get("passport_expiry"))
    if pexp:
        add(pexp - timedelta(days=182), "Last re-entry date with 6 months of passport validity", "R5")
        add(pexp, "Passport expires", "R5")
    pend = _d(profile.get("program_end"))
    if pend:
        add(pend - timedelta(days=90), "OPT filing window opens (I-765)", "R7")
        add(pend, "I-20 program end date", "R6")
        add(pend + timedelta(days=60), "OPT filing window closes; 60-day grace period ends", "R6")
    add(return_date, "Planned re-entry", None, kind="trip")
    out.sort(key=lambda e: e["date"])
    return out


def ics(events: list[dict]) -> str:
    """iCalendar file with all-day events; imports into Apple Calendar offline."""
    stamp = date.today().strftime("%Y%m%d") + "T000000Z"
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//CaseNote//on-device//EN", "CALSCALE:GREGORIAN"]
    for i, e in enumerate(events):
        if e["kind"] == "trip" or e["state"] == "past":
            continue
        d = e["date"].replace("-", "")
        nxt = (date.fromisoformat(e["date"]) + timedelta(days=1)).strftime("%Y%m%d")
        src = RULES_BY_ID[e["rule"]]["url"] if e["rule"] else ""
        lines += ["BEGIN:VEVENT", f"UID:casenote-{i}-{d}@local", f"DTSTAMP:{stamp}",
                  f"DTSTART;VALUE=DATE:{d}", f"DTEND;VALUE=DATE:{nxt}",
                  f"SUMMARY:{e['title']}", f"DESCRIPTION:Rule {e['rule']}. Source: {src}",
                  "BEGIN:VALARM", "TRIGGER:-P30D", "ACTION:DISPLAY", f"DESCRIPTION:{e['title']} in 30 days", "END:VALARM",
                  "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


# ---------- status path: F-1 -> CPT -> OPT -> STEM OPT -> H-1B -> green card ----------
# Rule text below is checked against the cited official pages (see README "Rules").
PATH_RULES = [
    {"id": "R8", "zh": "CPT：一般须合法全日制就读满一个完整学年（要求更早实习的部分研究生项目除外），须是既定课程的组成部分，由 DSO 在 SEVIS 中批准并印在 I-20 上；累计一年全职 CPT（每周超过 20 小时）将失去 OPT 资格。",
     "en": "CPT: generally needs one full academic year of lawful full-time enrollment (some graduate programs requiring earlier training are an exception); it must be an integral part of an established curriculum and is authorized by the DSO in SEVIS and printed on the I-20; one year of full-time CPT (more than 20 hours a week) eliminates OPT eligibility.",
     "source_name": "Study in the States (DHS): F-1 Curricular Practical Training", "url": "https://studyinthestates.dhs.gov/sevis-help-hub/student-records/fm-student-employment/f-1-curricular-practical-training-cpt"},
    {"id": "R9", "zh": "STEM OPT：学位在 DHS STEM 名单上的 OPT 学生可申请一次 24 个月延期；雇主须参加 E-Verify，DSO 推荐前需完成 I-983；I-765 最早在当前 OPT 卡到期前 90 天递交、不晚于 OPT 结束日，且须在 DSO 推荐后 60 天内送达 USCIS；宽限期内不能申请。",
     "en": "STEM OPT: students on post-completion OPT with a degree on the DHS STEM list can get a one-time 24-month extension; the employer must use E-Verify and a Form I-983 is required before the DSO recommends it; file the I-765 up to 90 days before the current OPT card expires and no later than its end date, and USCIS must receive it within 60 days of the DSO recommendation; not during the grace period.",
     "source_name": "USCIS: OPT Extension for STEM Students", "url": "https://www.uscis.gov/working-in-the-united-states/students-and-exchange-visitors/optional-practical-training-extension-for-stem-students-stem-opt"},
    {"id": "R10", "zh": "OPT 失业天数：毕业后 OPT 最多 90 天；STEM OPT 总计 150 天（包含此前已用的天数，即多 60 天）。",
     "en": "OPT unemployment: post-completion OPT allows 90 days; STEM OPT allows 150 days in total, including days already used (60 more).",
     "source_name": "Study in the States (DHS): Unemployment Counter", "url": "https://studyinthestates.dhs.gov/sevis-help-hub/student-records/fm-student-employment/unemployment-counter"},
    {"id": "R11", "zh": "H-1B：雇主须先在 USCIS 每年公布的电子注册期注册（FY2027 为 2026 年 3 月 4 日至 19 日），中签后才能递交，工作开始日不早于 10 月 1 日；自 FY2027 起按工资级别加权抽签。及时递交的 H-1B 抽签申请可将 F-1 身份和 OPT 工作许可延至次年 4 月 1 日（cap-gap）。",
     "en": "H-1B: the employer first registers during USCIS's annual registration period (FY2027 ran March 4 to 19, 2026); only selected registrations can be filed, with a start date of October 1 or later; selection is weighted by wage level from FY2027. A timely filed cap petition extends F-1 status and OPT work authorization to April 1 (cap-gap).",
     "source_name": "USCIS: H-1B Cap Season", "url": "https://www.uscis.gov/working-in-the-united-states/temporary-workers/h-1b-specialty-occupations/h-1b-cap-season"},
    {"id": "R12", "zh": "绿卡：USCIS 列出的途径包括职业移民 EB-1、EB-2（含国家利益豁免）、EB-3，亲属移民等；适合哪条需律师评估。",
     "en": "Green card: USCIS lists employment-based EB-1, EB-2 (including the National Interest Waiver) and EB-3, family-based and other categories; which one fits needs an attorney's assessment.",
     "source_name": "USCIS: Green Card Eligibility Categories", "url": "https://www.uscis.gov/green-card/green-card-eligibility-categories"},
]
RULES.extend(PATH_RULES)
RULES_BY_ID.update({r["id"]: r for r in PATH_RULES})

STEM_HINTS = ("ENGINEERING", "COMPUTER", "MATHEMATIC", "STATISTIC", "PHYSICS", "CHEMISTRY", "BIOLOG",
              "DATA SCIENCE", "INFORMATION SCIENCE", "ROBOTICS", "ACTUARIAL")


def _add_months(d: date, m: int) -> date:
    y, mo = divmod(d.month - 1 + m, 12)
    day = min(d.day, [31, 29 if (d.year + y) % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mo])
    return date(d.year + y, mo + 1, day)


def path(profile: dict, today: date | None = None) -> list[dict]:
    """The usual route from F-1 onward, with dates computed from this person's documents."""
    today = today or date.today()
    start, end = _d(profile.get("program_start")), _d(profile.get("program_end"))
    if not (start and end):
        return []
    major = (profile.get("major") or "").upper()
    stem = any(h in major for h in STEM_HINTS)

    def st(a, b=None):
        if b and a <= today <= b:
            return "now"
        return "done" if (b or a) < today else "later"

    out = []
    out.append({"stage": "F-1 student", "state": st(start, end),
                "when": f"{start.isoformat()} to {end.isoformat()}",
                "detail": f"Studying {(profile.get('major') or 'your program').title()} at {(profile.get('school') or 'your school').title()}.", "rule": None})
    cpt_from = _add_months(start, 12)
    if cpt_from < end:
        out.append({"stage": "CPT (internships during school)", "state": "now" if cpt_from <= today < end else ("later" if today < cpt_from else "done"),
                    "when": f"from about {cpt_from.isoformat()}" if today < cpt_from else "available now, with DSO authorization",
                    "detail": "Each job needs DSO authorization on your I-20. One year of full-time CPT (over 20 hours a week) removes OPT eligibility.", "rule": "R8"})
    opt_open, opt_close = end - timedelta(days=90), end + timedelta(days=60)
    out.append({"stage": "OPT (12 months of work after graduation)", "state": st(opt_open, opt_close),
                "when": f"file I-765 between {opt_open.isoformat()} and {opt_close.isoformat()}",
                "detail": "Up to 90 days of unemployment are allowed during OPT [R10].", "rule": "R7"})
    opt_end = _add_months(end, 12)  # approximate: the real dates are on the OPT card
    if stem:
        out.append({"stage": "STEM OPT extension (24 more months)", "state": st(opt_end - timedelta(days=90), opt_end),
                    "when": f"apply from about {(opt_end - timedelta(days=90)).isoformat()} (90 days before the OPT card ends)",
                    "detail": ("Electrical engineering (CIP 14.10) is on the DHS STEM list" if "ELECTRICAL" in major else f"{profile.get('major').title()} looks like a STEM field") + "; confirm the CIP code on your I-20. Employer must use E-Verify; needs Form I-983. Unemployment limit becomes 150 days.", "rule": "R9"})
    last = _add_months(opt_end, 24) if stem else opt_end
    years = [y for y in range(end.year, last.year + 1) if date(y, 3, 31) >= today and date(y, 3, 1) <= last]
    if years:
        out.append({"stage": "H-1B (employer-sponsored work visa)", "state": "later",
                    "when": "registration in March " + ", ".join(str(y) for y in years[:3]) + (" (exact dates announced by USCIS)"),
                    "detail": "Your employer registers you; selection is weighted by wage level. If selected and filed on time, cap-gap keeps your F-1 status and OPT work authorization until April 1; H-1B work starts October 1 or later.", "rule": "R11"})
    out.append({"stage": "Green card (permanent residence)", "state": "info", "when": "talk to an attorney",
                "detail": "Common routes: employer sponsorship (EB-2, EB-3), EB-2 National Interest Waiver, EB-1, or family. CaseNote can prepare the packet.", "rule": "R12"})
    return out
