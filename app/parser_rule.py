"""
Rule-based résumé parser tuned for the sample PDF.
Extracts experience, education, projects with titles & URLs.
"""

from __future__ import annotations
import json, re
from typing import Dict, List
from schema_resume import RESUME_SCHEMA
from cleaner import (
    decamel,
    smart_split,
    normalise_phone,
    expand_username_url,
    clean_resume,
)

HDR = re.compile(r"^(WORK EXPERIENCE|EDUCATION|SKILLS|PROJECTS)\b", re.I)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"\d{7,}")
STAR = r"[∗*⋆✱]"

STOP = {
    "core",
    "skills",
    "programming",
    "languages",
    "libraries",
    "frameworks",
    "tools",
    "platforms",
    "soft",
    "extracurricular",
}


def parse_resume_rule(raw: str) -> Dict:
    out = json.loads(json.dumps(RESUME_SCHEMA))
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]

    # header
    out["name"] = lines[0]
    out["headline"] = decamel(lines[1]) if len(lines) > 1 else ""

    # contact block
    head = "\n".join(lines[:20])
    if m := EMAIL.search(head):
        out["contact"]["email"] = m.group()
    if m := PHONE.search(head):
        out["contact"]["phone"] = normalise_phone(m.group())

    out["contact"]["github"] = expand_username_url(
        next((l for l in lines if "github" in l.lower()), ""), "github.com"
    )
    out["contact"]["linkedin"] = expand_username_url(
        next((l for l in lines if "linkedin" in l.lower()), ""), "linkedin.com"
    )

    # section dispatcher
    sec, buf = None, []
    for ln in lines[2:]:
        if m := HDR.match(ln):
            _flush(sec, buf, out)
            sec, buf = m.group(1).upper(), []
        else:
            buf.append(ln)
    _flush(sec, buf, out)
    return clean_resume(out)


# ───────────────────────────────────────── helpers ──
def _flush(sec: str | None, buf: List[str], o: Dict):
    if not sec or not buf:
        return
    if sec == "SKILLS":
        toks = [decamel(t) for t in smart_split(" ".join(buf))]
        o["skills"]["core"] = [t for t in toks if t.lower() not in STOP and len(t) < 25]
    elif sec == "WORK EXPERIENCE":
        _jobs(buf, o["experience"])
    elif sec == "EDUCATION":
        _edu(buf, o["education"])
    elif sec == "PROJECTS":
        _project(buf, o["projects"])


def _jobs(lines: List[str], tgt: List[Dict]):
    i = 0
    while i < len(lines):
        pat = re.match(rf"^(.*?)\s+{STAR}\s+(.*)$", lines[i])
        if pat:
            title, loc = [decamel(x) for x in pat.groups()]
            i += 1
            comp, start, end = "", "", ""
            if i < len(lines) and " z " in lines[i]:
                comp, dates = [x.strip() for x in lines[i].split(" z ", 1)]
                comp = decamel(comp)
                if "–" in dates or "-" in dates:
                    start, end = [x.strip() for x in re.split(r"[–-]", dates, 1)]
                i += 1
            bullets = []
            while i < len(lines) and lines[i].startswith(("•", "-")):
                bullets.append(decamel(lines[i].lstrip("•- ")))
                i += 1
            tgt.append(
                {
                    "title": title,
                    "company": comp,
                    "location": loc,
                    "start": start,
                    "end": end,
                    "bullets": bullets,
                }
            )
        else:
            i += 1


def _edu(lines: List[str], tgt: List[Dict]):
    i = 0
    while i < len(lines):
        pat = re.match(rf"^(.*?)\s+{STAR}\s+(.*)$", lines[i])
        if pat:
            degree, loc = [decamel(x) for x in pat.groups()]
            i += 1
            school, start, end = "", "", ""
            if i < len(lines) and " z " in lines[i]:
                school, dates = [x.strip() for x in lines[i].split(" z ", 1)]
                school = decamel(school)
                if "–" in dates or "-" in dates:
                    start, end = [x.strip() for x in re.split(r"[–-]", dates, 1)]
                i += 1
            bullets = []
            while i < len(lines) and lines[i].startswith(("•", "-")):
                bullets.append(decamel(lines[i].lstrip("•- ")))
                i += 1
            tgt.append(
                {
                    "degree": degree,
                    "school": school,
                    "location": loc,
                    "start": start,
                    "end": end,
                    "bullets": bullets,
                }
            )
        else:
            i += 1


def _project(lines: List[str], tgt: List[Dict]):
    """All lines in the PROJECTS buf belong to one project block."""
    title = decamel(lines[0])
    url = ""
    bullets = []
    for ln in lines[1:]:
        if ("github.com" in ln) or ("§" in ln) or ("http" in ln):
            url = ln.strip("§ ").strip()
        elif ln.startswith(("•", "-")):
            bullets.append(decamel(ln.lstrip("•- ")))
    tgt.append({"title": title, "url": url, "bullets": bullets})
