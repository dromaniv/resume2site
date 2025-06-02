"""
LLM-based résumé parser.

• Supports multiple LLM providers (Ollama with Devstral, OpenAI with GPT models)
• Caches responses in .cache/<sha256>.json so the model is
  queried only once per unique resume text.
• Runs clean_resume() to de-camel titles, format phone, etc.
"""

from __future__ import annotations
import json, os, re, textwrap
from pathlib import Path
from llm_client import chat

from schema_resume import RESUME_SCHEMA
from cleaner import clean_resume
from utils import _sha

# Model and cache configuration
try:
    from config import get_model_for_provider
    _MODEL = get_model_for_provider()
except ImportError:
    _MODEL = "devstral"  # Fallback if config is not available

_CACHE_DIR = Path(".cache")
_CACHE_DIR.mkdir(exist_ok=True)

_SYSTEM_PROMPT = textwrap.dedent(
    f"""
You are an expert résumé parser.
Output ONLY valid JSON conforming to this schema (no markdown fences):

{json.dumps(RESUME_SCHEMA, indent=2)}
"""
)

_JSON_FINDER = re.compile(r"\{.*\}", re.S)


def _extract_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        if m := _JSON_FINDER.search(raw):
            return json.loads(m.group())
        raise


def parse_resume_llm(raw_text: str) -> dict:
    cache_path = _CACHE_DIR / f"{_sha(raw_text)}.json"

    if cache_path.exists():
        return json.loads(cache_path.read_text())

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": raw_text},
    ]
    rsp = chat(model=_MODEL, messages=messages)
    payload = rsp.message.content.strip().strip("`")
    data = _extract_json(payload)
    data = clean_resume(data)

    cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return data
