"""
Shared clean-ups and schema normalisation.
"""
from __future__ import annotations
import re, unicodedata
from typing import List, Dict, Any

_CAMEL  = re.compile(r"(?<=[a-z])(?=[A-Z])")
_DIGITS = re.compile(r"[^\d]")

# ───────────────────────────────────────── helpers ──
def decamel(s: str) -> str:
    return _CAMEL.sub(" ", s or "").strip()

def smart_split(text: str) -> List[str]:
    return re.split(r"[,\s]+", unicodedata.normalize("NFKC", text).strip())

def normalise_phone(raw: str) -> str:
    digits = _DIGITS.sub("", raw or "")
    if digits.startswith("48") and len(digits) >= 11:
        return "+48 " + " ".join([digits[2:5], digits[5:8], digits[8:11]])
    if len(digits) == 9:
        return "+48 " + " ".join([digits[:3], digits[3:6], digits[6:]])
    return raw

def expand_username_url(token: str, domain: str) -> str:
    token = token.strip()
    if token.startswith("http"):
        return token
    return f"https://{domain}/{token.lstrip('@').split('/')[-1]}" if token else ""

def _sentences(raw: str | list[str]) -> List[str]: # Allow list of strings as input
    """Turn long description into bullet sentences."""
    if isinstance(raw, list):
        raw = " ".join(raw) # Join list elements into a single string
    bits = re.split(r"[•\u2022\-–]\s*|\.\s+", (raw or "").strip()) # Ensure raw is not None before stripping
    return [decamel(x) for x in bits if x]

# ───────────────────────────────────────── cleaner ──
def clean_resume(r: Dict[str, Any]) -> Dict[str, Any]:
    # headline
    r["headline"] = decamel(r.get("headline", ""))

    # contact
    if ph := r.get("contact", {}).get("phone"):
        r["contact"]["phone"] = normalise_phone(ph)

    # experience
    for j in r.get("experience", []):
        j["title"]    = decamel(j.pop("title", j.pop("position", "")))
        j["company"]  = decamel(j.get("company", ""))
        j["location"] = decamel(j.get("location", ""))
        j["start"]    = j.pop("start", j.pop("startDate", ""))
        j["end"]      = j.pop("end",   j.pop("endDate",   ""))
        description = j.pop("description", None) # Pop description
        if description and not j.get("bullets"):
            j["bullets"] = _sentences(description) # Pass it to _sentences
            

    # education
    for e in r.get("education", []):
        deg  = e.pop("degree", "")
        field= e.pop("fieldOfStudy", "")
        e["degree"]   = decamel(" ".join([deg, field]).strip())
        e["school"]   = decamel(e.get("school", ""))
        e["location"] = decamel(e.get("location", ""))
        e["start"]    = e.pop("start", e.pop("startDate", ""))
        e["end"]      = e.pop("end",   e.pop("endDate",   ""))
        if "description" in e and not e.get("bullets"):
            e["bullets"] = _sentences(e.pop("description"))

    # projects → guarantee dict shape
    fixed = []
    for p in r.get("projects", []):
        if isinstance(p, str):
            fixed.append({"title": decamel(p), "url": "", "bullets": []})
        else:
            fixed.append({
                "title": decamel(p.get("title") or p.get("name", "")),
                "url":   p.get("url",  p.get("link", "")),
                "bullets": (
                    p.get("bullets") or _sentences(p.get("description", ""))
                ),
            })
    r["projects"] = fixed

    # skills – drop headers & long junk tokens
    for cat, lst in list(r.get("skills", {}).items()):
        r["skills"][cat] = [decamel(x) for x in lst
                            if x and len(x) < 30 and "skill" not in x.lower()]

    # purge empties
    r["experience"] = [j for j in r["experience"] if j.get("title")]
    r["education"]  = [e for e in r["education"]  if e.get("degree")]
    r["projects"]   = [p for p in r["projects"]   if p.get("title")]
    return r