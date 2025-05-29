from __future__ import annotations

import base64
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

import tempfile
from pathlib import Path

from PIL import Image  # type: ignore

from .common_utils import (
    gpt_clean_text,
    normalize_price,
    detect_currency,
    safe_json_parse,
)
from .debug_utils import save_debug, save_debug_image, set_output_subdir

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
    """Parse ``pdf_path`` using GPT-4o vision."""

    set_output_subdir(Path(pdf_path).stem)

    try:
        from pdf2image import convert_from_path  # type: ignore
    except Exception as exc:  # pragma: no cover - optional deps missing
        logger.error("pdf2image unavailable: %s", exc)
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

    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        os.environ.setdefault("OPENAI_API_KEY", api_key)

    try:
        import openai
    except Exception as exc:  # pragma: no cover - import errors
        logger.error("OpenAI import failed: %s", exc)
        return pd.DataFrame()

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o")

    prompt = (
        "Aşağıdaki fiyat listesi sayfasındaki tablodan 'Malzeme Kodu', "
        "'Açıklama', 'Fiyat', 'Birim' ve 'Kutu Adedi' alanlarını içeren bir "
        "JSON dizisi üret. Sadece geçerli JSON döndür."
    )

    rows = []
    page_summary: list[dict[str, object]] = []
    for idx, img in enumerate(images, start=1):
        start_len = len(rows)
        status = "success"
        note = None
        img_path = save_debug_image("page_image", idx, img)
        tmp_path = img_path
        created_tmp = False
        if tmp_path is None:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            img.save(tmp.name, format="PNG")
            tmp.close()
            tmp_path = Path(tmp.name)
            created_tmp = True
        try:
            with open(tmp_path, "rb") as f:
                image_bytes = f.read()
            img_base64 = base64.b64encode(image_bytes).decode()
            resp = openai.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": "data:image/png;base64," + img_base64},
                            },
                        ],
                    }
                ],
                temperature=0,
            )
            content = resp.choices[0].message.content
            save_debug("llm_response", idx, content or "")
        except Exception as exc:  # pragma: no cover - request errors
            logger.error("OpenAI request failed on page %d: %s", idx, exc)
            status = "error"
            note = str(exc)
            content = None
        finally:
            if created_tmp:
                try:
                    os.remove(tmp_path)
                except Exception as exc:  # pragma: no cover - cleanup errors
                    logger.debug("temp file cleanup failed: %s", exc)

        cleaned = gpt_clean_text(content) if content else "[]"
        items = safe_json_parse(cleaned)
        if items is None:
            logger.error("LLM JSON parse failed on page %d", idx)
            status = "error"
            note = "parse error"
            items = []

        items = items if isinstance(items, list) else [items]
        for item in items:
            descr = item.get("Açıklama")
            price_raw = str(item.get("Fiyat", "")).strip()
            rows.append(
                {
                    "Malzeme_Kodu": item.get("Malzeme Kodu"),
                    "Descriptions": descr,
                    "Fiyat": normalize_price(price_raw),
                    "Birim": item.get("Birim"),
                    "Kutu_Adedi": item.get("Kutu Adedi"),
                    "Para_Birimi": detect_currency(price_raw),
                    "Sayfa": idx,
                }
            )

        added = len(rows) - start_len
        if status == "success" and added == 0:
            status = "empty"
        page_summary.append(
            {
                "page_number": idx,
                "rows": added,
                "status": status,
                "note": note,
            }
        )

    df = pd.DataFrame(rows)
    if hasattr(df, "empty") and not df.empty:
        base = Path(pdf_path).stem
        df["Record_Code"] = (
            base
            + "|"
            + df["Sayfa"].astype(str)
            + "|"
            + (df.groupby("Sayfa").cumcount() + 1).astype(str)
        )
    try:
        df.page_summary = page_summary
    except Exception:  # pragma: no cover - non DataFrame stubs
        pass
    set_output_subdir(None)
    return df

