from __future__ import annotations

import json
import logging
import os
from typing import Iterable, Sequence
from dotenv import load_dotenv

try:
    load_dotenv("../..")
except TypeError:  # pragma: no cover - allow stub without args
    load_dotenv()

import pandas as pd

from .common_utils import gpt_clean_text

logger = logging.getLogger("smart_price")


def _range_bounds(pages: Sequence[int] | range | None) -> tuple[int | None, int | None]:
    """Return first and last page numbers from ``pages``."""
    if not pages:
        return None, None
    try:
        start = pages.start  # type: ignore[attr-defined]
        end = pages.stop - 1  # type: ignore[attr-defined]
    except AttributeError:
        seq = list(pages)  # type: ignore[arg-type]
        if not seq:
            return None, None
        start, end = min(seq), max(seq)
    return start, end


def parse(pdf_path: str, page_range: Iterable[int] | range | None = None) -> pd.DataFrame:
    """Parse ``pdf_path`` using OCR followed by an LLM."""

    try:
        from pdf2image import convert_from_path  # type: ignore
        import pytesseract  # type: ignore
    except Exception as exc:  # pragma: no cover - optional deps missing
        logger.error("OCR dependencies unavailable: %s", exc)
        return pd.DataFrame()

    try:
        kwargs = {"dpi": 300}
        first, last = _range_bounds(page_range)
        if first is not None:
            kwargs["first_page"] = first
        if last is not None:
            kwargs["last_page"] = last
        images = convert_from_path(pdf_path, **kwargs)
    except Exception as exc:  # pragma: no cover - conversion errors
        logger.error("pdf2image failed for %s: %s", pdf_path, exc)
        return pd.DataFrame()

    ocr_text_parts = []
    for idx, img in enumerate(images, start=1):
        try:
            text = pytesseract.image_to_string(img, lang="tur")
            logger.debug("OCR page %d length %d", idx, len(text))
            if text:
                ocr_text_parts.append(text)
        except Exception as exc:  # pragma: no cover - OCR errors
            logger.error("OCR failed on page %d: %s", idx, exc)

    ocr_text = "\n".join(ocr_text_parts).strip()
    if not ocr_text:
        logger.info("No OCR text produced from %s", pdf_path)
        return pd.DataFrame()

    prompt = (
        "Extract JSON [{code, price, descr}] from the text below. "
        "Return only valid JSON.\n\n" + ocr_text
    )

    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        os.environ.setdefault("OPENAI_API_KEY", api_key)

    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover - import errors
        logger.error("OpenAI import failed: %s", exc)
        return pd.DataFrame()

    client = OpenAI(api_key=api_key)

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = resp.choices[0].message.content
    except Exception as exc:  # pragma: no cover - request errors
        logger.error("OpenAI request failed: %s", exc)
        return pd.DataFrame()

    try:
        cleaned = gpt_clean_text(content)
        items = json.loads(cleaned)
    except Exception as exc:  # pragma: no cover - JSON errors
        logger.error("LLM JSON parse failed: %s", exc)
        return pd.DataFrame()

    rows = []
    for item in items if isinstance(items, list) else [items]:
        descr = item.get("descr")
        price = item.get("price")
        if descr is None or price is None:
            continue
        rows.append(
            {
                "Malzeme_Kodu": item.get("code"),
                "Descriptions": descr,
                "Fiyat": price,
                "Para_Birimi": item.get("currency"),
            }
        )

    return pd.DataFrame(rows)

