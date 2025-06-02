from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

from smart_price import config


def load_extraction_guide(path: str | None = None) -> List[Dict[str, Any]]:
    """Return guide entries from ``path``.

    If ``path`` is ``None`` try ``config.EXTRACTION_GUIDE_PATH`` and fallback
    to ``extraction_guide.csv`` or ``extraction_guide.json`` under the
    repository root. Parsing errors result in an empty list.
    """
    if path is None:
        path = str(getattr(config, "EXTRACTION_GUIDE_PATH", ""))
    if not path:
        root = Path(__file__).resolve().parents[2]
        for name in ("extraction_guide.csv", "extraction_guide.json"):
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
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def prompts_for_pdf(pdf_name: str, path: str | None = None) -> Dict[int, str] | None:
    """Return page prompts for ``pdf_name`` from the guide.

    The returned mapping may contain a ``0`` key representing a default prompt
    for all pages.
    """
    guide = load_extraction_guide(path)
    if not guide:
        return None
    stem = Path(pdf_name).stem.lower()
    mapping: Dict[int, str] = {}
    for row in guide:
        file_field = row.get("pdf") or row.get("file") or row.get("name")
        if not file_field:
            continue
        if Path(file_field).stem.lower() != stem:
            continue
        prompt = row.get("prompt")
        if not prompt:
            continue
        page_val = row.get("page")
        if page_val in (None, "", "null"):
            mapping[0] = prompt
        else:
            try:
                mapping[int(page_val)] = prompt
            except (ValueError, TypeError):
                continue
    return mapping or None
