from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
import logging

from smart_price import config
from utils.prompt_builder import get_prompt_for_file
from .extract_excel import (
    _RAW_CODE_HEADERS,
    _RAW_DESC_HEADERS,
    _RAW_SHORT_HEADERS,
    _RAW_PRICE_HEADERS,
    _RAW_CURRENCY_HEADERS,
    _RAW_MAIN_HEADERS,
    _RAW_SUB_HEADERS,
)

# Concise hint listing all possible raw column headers that may appear in Excel
# or PDF tables. This is added to LLM prompts so it knows which column labels to
# look out for when parsing tabular data.
RAW_HEADER_HINT = (
    "Olası kolon başlıkları; kodlar: "
    + ", ".join(_RAW_CODE_HEADERS + _RAW_SHORT_HEADERS)
    + "; açıklamalar: "
    + ", ".join(_RAW_DESC_HEADERS)
    + "; fiyatlar: "
    + ", ".join(_RAW_PRICE_HEADERS)
    + "; para birimleri: "
    + ", ".join(_RAW_CURRENCY_HEADERS)
    + "; ana başlıklar: "
    + ", ".join(_RAW_MAIN_HEADERS)
    + "; alt başlıklar: "
    + ", ".join(_RAW_SUB_HEADERS)
    + "."
)

logger = logging.getLogger("smart_price")


def _parse_md_guide(path: Path) -> List[Dict[str, Any]]:
    """Parse ``extraction_guide.md`` into a list of prompt entries.

    Each top level ``##`` heading represents a brand or PDF name. The
    function extracts the text until the next heading while stripping code
    blocks and sub-headings so that only the plain instructions remain.
    """

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    sections: List[Tuple[str, List[str]]] = []
    current: Tuple[str, List[str]] | None = None
    for line in lines:
        if line.startswith("## "):
            if current:
                sections.append(current)
            current = (line[3:].strip(), [])
        else:
            if current:
                current[1].append(line)
    if current:
        sections.append(current)

    result = []
    for title, body_lines in sections:
        cleaned: List[str] = []
        in_code = False
        for ln in body_lines:
            lstripped = ln.lstrip()
            if lstripped.startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            if lstripped.startswith("###"):
                continue
            if "JSON" in lstripped.upper():
                continue
            if lstripped.startswith("#"):
                continue
            if lstripped.startswith(('-', '*')):
                lstripped = lstripped.lstrip('-*').strip()
            if lstripped:
                cleaned.append(lstripped)
        body = "\n".join(cleaned).strip()
        result.append({"pdf": title, "page": None, "prompt": body})

    return result



def load_extraction_guide(path: str | None = None) -> List[Dict[str, Any]]:
    """Return guide entries from ``path``.

    If ``path`` is ``None`` try ``config.EXTRACTION_GUIDE_PATH`` and fallback
    to ``extraction_guide.md``, ``extraction_guide.csv`` or ``extraction_guide.json``
    under the repository root. Parsing errors result in an empty list.
    """
    if path is None:
        path = str(getattr(config, "EXTRACTION_GUIDE_PATH", ""))
    if not path:
        root = Path(__file__).resolve().parents[2]
        for name in ("extraction_guide.md", "extraction_guide.csv", "extraction_guide.json"):
            candidate = root / name
            if candidate.exists():
                path = str(candidate)
                break
    if not path:
        return []
    p = Path(path)
    try:
        if p.suffix.lower() == ".csv":
            with p.open(encoding="utf-8") as fh:
                return list(csv.DictReader(fh))
        if p.suffix.lower() == ".json":
            return json.loads(p.read_text(encoding="utf-8"))
        if p.suffix.lower() in {".md", ".markdown"}:
            return _parse_md_guide(p)
        return []
    except Exception:
        return []


def prompts_for_pdf(pdf_name: str) -> str:
    """DEPRECATED – use :func:`utils.prompt_builder.get_prompt_for_file`."""
    return get_prompt_for_file(pdf_name)
