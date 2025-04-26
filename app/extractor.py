"""
PDF ➜ raw text
– strips `(cid:N)` glyph artifacts
– suppresses verbose CropBox warnings from pdfplumber/pdfminer
"""
from pathlib import Path
import re, logging, warnings, pdfplumber

# silence noisy PDF logging
logging.getLogger("pdfplumber").setLevel(logging.ERROR)
logging.getLogger("pdfminer").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=UserWarning, module="pdfminer")

_CID_RE = re.compile(r"\(cid:\d+\)")

def pdf_to_text(pdf_path: str | Path) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    return _CID_RE.sub("", "\n".join(pages))