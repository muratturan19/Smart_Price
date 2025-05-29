from __future__ import annotations

import base64
import logging
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable, Sequence, TYPE_CHECKING
from dotenv import load_dotenv

try:
    load_dotenv("../..")
except TypeError:  # pragma: no cover - allow stub without args
    load_dotenv()

import pandas as pd

import tempfile
from pathlib import Path


from .common_utils import (
    gpt_clean_text,
    normalize_price,
    detect_currency,
    safe_json_parse,
)
from .debug_utils import save_debug, save_debug_image, set_output_subdir

if TYPE_CHECKING:  # pragma: no cover - type hints only
    from PIL import Image  # noqa: F401

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


def parse(
    pdf_path: str,
    page_range: Iterable[int] | range | None = None,
    *,
    output_name: str | None = None,
) -> pd.DataFrame:
    """Parse ``pdf_path`` using GPT-4o vision.

    Parameters
    ----------
    pdf_path : str
        Path to the PDF file to parse.
    page_range : iterable of int or range, optional
        Pages to include when converting the PDF to images.
    output_name : str, optional
        Name of the debug output directory under ``LLM_Output_db``.  Defaults
        to ``Path(pdf_path).stem``.
    """

    if output_name is None:
        output_name = Path(pdf_path).stem

    set_output_subdir(output_name)
    total_start = time.time()

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
        start_convert = time.time()
        images = convert_from_path(pdf_path, **kwargs)
        logger.info(
            "pdf2image.convert_from_path took %.2fs for %d pages",
            time.time() - start_convert,
            len(images),
        )
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

    rows: list[dict[str, object]] = []
    page_summary: list[dict[str, object]] = []

    lock = threading.Lock()
    running = 0

    def process_page(args: tuple[int, "Image.Image"]):
        nonlocal running
        idx, img = args
        start = time.time()
        with lock:
            running += 1
            current = running
        logger.info("LLM request start page %d (running=%d)", idx, current)

        page_rows: list[dict[str, object]] = []
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
            api_start = time.time()
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
            logger.info(
                "OpenAI request for page %d took %.2fs", idx, time.time() - api_start
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
            page_rows.append(
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

        added = len(page_rows)
        if status == "success" and added == 0:
            status = "empty"

        summary = {
            "page_number": idx,
            "rows": added,
            "status": status,
            "note": note,
        }
        dur = time.time() - start
        with lock:
            running -= 1
            current = running
        logger.info(
            "LLM request end page %d (running=%d, %.2fs)", idx, current, dur
        )
        return idx, page_rows, summary

    workers = int(os.getenv("SMART_PRICE_LLM_WORKERS", "5"))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(process_page, (i, img)) for i, img in enumerate(images, start=1)]
        results = [f.result() for f in futures]

    results.sort(key=lambda r: r[0])
    for _idx, rows_out, summary in results:
        rows.extend(rows_out)
        page_summary.append(summary)

    df = pd.DataFrame(rows)
    if hasattr(df, "columns") and "Kutu_Adedi" in getattr(df, "columns", []):
        try:
            df["Kutu_Adedi"] = df["Kutu_Adedi"].astype("string")
        except Exception:  # pragma: no cover - DataFrame stub
            pass
    if hasattr(df, "empty") and not df.empty:
        base = Path(pdf_path).stem
        df["Record_Code"] = (
            base
            + "|"
            + df["Sayfa"].astype(str)
            + "|"
            + (df.groupby("Sayfa").cumcount() + 1).astype(str)
        )
    if hasattr(df, "__dict__"):
        object.__setattr__(df, "page_summary", page_summary)
    total_dur = time.time() - total_start
    logger.info("Finished %s with %d rows in %.2fs", pdf_path, len(df), total_dur)
    set_output_subdir(None)
    return df

