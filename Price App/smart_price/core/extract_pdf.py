from __future__ import annotations

import os
import tempfile
from typing import IO, Any, Optional, Sequence, Callable
import logging
from datetime import datetime
import difflib
import unicodedata

import pandas as pd

try:
    from dotenv import load_dotenv, find_dotenv
except ImportError:  # pragma: no cover - support missing find_dotenv
    from dotenv import load_dotenv

    def find_dotenv() -> str:
        return ""


try:
    load_dotenv(dotenv_path=find_dotenv())
except TypeError:  # pragma: no cover - allow stub without args
    load_dotenv(dotenv_path=find_dotenv())

# Optional OCR dependencies are imported lazily within extract_from_pdf
import re
from .common_utils import (
    normalize_price,
    detect_currency,
    normalize_currency,
    detect_brand,
    gpt_clean_text,
    safe_json_parse,
    validate_output_df,
)
import time
from . import ocr_llm_fallback
from pathlib import Path
from .debug_utils import save_debug, set_output_subdir
from .prompt_utils import prompts_for_pdf
from .token_utils import log_token_counts
from .github_upload import upload_folder, _sanitize_repo_path

PAGE_IMAGE_EXT = ".jpg"

MIN_CODE_RATIO = 0.70
CODE_RE = re.compile(r"^([A-ZÇĞİÖŞÜ0-9][A-ZÇĞİÖŞÜ0-9\-/]{1,})", re.I)

# Token accumulator used during extraction
TOKEN_ACCUM = {"input": 0, "output": 0}

logger = logging.getLogger("smart_price")


def _norm(s: Any) -> str:
    """Normalize ``s`` for fuzzy header matching."""
    return unicodedata.normalize("NFKD", str(s)).lower()


def header_match(
    cell: Any, candidates: Sequence[str], *, match_type: str | None = None
) -> bool:
    """Return True if ``cell`` fuzzily matches any of ``candidates``."""
    norm_candidates = [_norm(c) for c in candidates]
    if difflib.get_close_matches(_norm(cell), norm_candidates, cutoff=0.75):
        logger.info("header_match", extra={"header": cell, "match_type": match_type})
        return True
    return False


_patterns = [
    re.compile(
        r"^(.*?)\s{2,}([\d\.,]+)\s*(?:TL|TRY|EUR|USD|\$|€)?$",
        re.MULTILINE | re.IGNORECASE,
    ),
    re.compile(
        r"([A-Z0-9\-\s/]{5,50})\s+([\d\.,]+)\s*(?:TL|TRY|EUR|USD|\$|€)?", re.IGNORECASE
    ),
    re.compile(r"Item Code:\s*(.*?)\s*Price:\s*([\d\.,]+)", re.IGNORECASE),
    re.compile(r"Ürün No:\s*(.*?)\s*Birim Fiyat:\s*([\d\.,]+)", re.IGNORECASE),
]


def _basename(fp: Any, filename: Optional[str] = None) -> str:
    """Return best-effort basename for a file path or buffer."""
    if filename:
        return os.path.basename(filename)
    if isinstance(fp, (str, bytes, os.PathLike)):
        return os.path.basename(fp)
    name = getattr(fp, "name", None)
    if isinstance(name, str):
        return os.path.basename(name)
    return ""


def extract_from_pdf(
    filepath: str | IO[bytes],
    *,
    filename: str | None = None,
    log: Optional[Callable[[str, str], None]] = None,
    prompt: str | dict[int, str] | None = None,
    progress_callback: Callable[[float], None] | None = None,
) -> pd.DataFrame:
    """Extract product information from a PDF file.

    Parameters
    ----------
    progress_callback : callable, optional
        Receives ``0-1`` progress updates for each processed page.
    """
    page_summary: list[dict[str, object]] = []
    TOKEN_ACCUM["input"] = 0
    TOKEN_ACCUM["output"] = 0
    
    def notify(message: str, level: str = "info") -> None:
        logger.info(message)
        if log:
            try:
                try:
                    log(message, level)
                except TypeError:
                    log(message)
            except Exception as exc:  # pragma: no cover - log callback errors
                logger.error("log callback failed: %s", exc)

    src = _basename(filepath, filename)
    output_stem = Path(src).stem
    sanitized_base = _sanitize_repo_path(output_stem)
    set_output_subdir(output_stem)
    guide_prompt = prompt or prompts_for_pdf(src)
    notify(f"Processing {src} started at {datetime.now():%Y-%m-%d %H:%M:%S}")
    total_start = time.time()


    def _llm_extract_from_image(text: str) -> list[dict]:
        """Use a language model to extract product names and prices from OCR text."""
        # pragma: no cover - not exercised in tests
        notify("LLM fazı başladı")
        # Environment already loaded at module import time
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or not text:
            notify("LLM returned no data")
            return []

        try:
            from openai import OpenAI
        except Exception as exc:  # pragma: no cover - optional dep missing
            notify(f"openai import failed: {exc}")
            notify("LLM returned no data")
            return []

        try:
            openai_max_retries = int(os.getenv("OPENAI_MAX_RETRIES", "0"))
        except Exception:
            openai_max_retries = 0
        try:  # pragma: no cover - openai may not expose this attr
            import openai as _openai
            _openai.api_requestor._DEFAULT_NUM_RETRIES = openai_max_retries
        except Exception:
            pass

        client = OpenAI(api_key=api_key, max_retries=openai_max_retries)

        model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
        excerpt = text[:200].replace("\n", " ")
        logger.debug("Using model %s on text excerpt: %r", model_name, excerpt)

        prompt = ocr_llm_fallback.DEFAULT_PROMPT

        save_debug("llm_prompt", 1, prompt)

        logger.debug("LLM prompt length: %d", len(prompt))
        logger.debug("LLM prompt excerpt: %r", prompt[:200])

        try:
            start_llm = time.time()
            resp = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            logger.info("OpenAI request took %.2fs", time.time() - start_llm)
            time.sleep(0.5)
            content = resp.choices[0].message.content
            save_debug("llm_response", 1, content)
            logger.debug("LLM raw response: %r", content.strip()[:200])
            try:
                cleaned = gpt_clean_text(content)
                items = safe_json_parse(cleaned)
                if items is None:
                    raise ValueError("parse failed")
                logger.debug("First parsed items: %r", items[:2])
                if not items:
                    excerpt = text[:100].replace("\n", " ")
                    notify(
                        f"no items parsed by {model_name}; OCR text excerpt: {excerpt!r}"
                    )
                    return []
            except Exception:
                notify(f"LLM returned invalid JSON: {content!r}")
                notify("LLM returned no data")
                return []
        except Exception as exc:
            notify(f"openai request failed: {exc}")
            notify("LLM returned no data")
            return []

        results = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("product") or "").strip()
            price_raw = str(item.get("price", "")).strip()
            val = normalize_price(price_raw)
            if name and val is not None:
                results.append(
                    {
                        "Malzeme_Adi": name,
                        "Fiyat": val,
                        "Para_Birimi": normalize_currency(detect_currency(price_raw)),
                    }
                )
        count = len(results)
        if count:
            notify(f"LLM parsed {count} items")
        else:
            notify("LLM returned no data")
        return results

    tmp_for_llm: str | None = None

    def cleanup() -> None:
        if tmp_for_llm:
            try:
                os.remove(tmp_for_llm)
            except Exception as exc:
                notify(f"temp file cleanup failed: {exc}")

    try:
        if isinstance(filepath, (str, bytes, os.PathLike)):
            path_for_llm = filepath
        else:
            try:
                filepath.seek(0)
            except Exception as exc:
                notify(f"seek failed: {exc}")
            pdf_bytes = filepath.read()
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            tmp.write(pdf_bytes)
            tmp.close()
            tmp_for_llm = tmp.name
            path_for_llm = tmp_for_llm

        notify("G\u00f6rseller olu\u015fturuluyor...")
        logger.info("==> BEGIN images_from_pdf")
        logger.info("==> BEGIN vision_loop")
        try:
            result = ocr_llm_fallback.parse(
                path_for_llm,
                output_name=output_stem if tmp_for_llm else None,
                prompt=guide_prompt,
                progress_callback=progress_callback,
            )
        except TypeError:
            try:
                result = ocr_llm_fallback.parse(
                    path_for_llm,
                    output_name=output_stem if tmp_for_llm else None,
                    prompt=guide_prompt,
                )
            except TypeError:
                result = ocr_llm_fallback.parse(path_for_llm)
        logger.info("==> END vision_loop rows=%s", len(result))
        logger.info(
            "==> END images_from_pdf pages=%s",
            len(getattr(result, "page_summary", [])),
        )
        notify("Sat\u0131rlar\u0131n g\u00f6rselleri haz\u0131rlan\u0131yor...")
        page_summary = getattr(result, "page_summary", [])
        tok = getattr(result, "token_counts", {})
        total_input_tokens = tok.get("input", TOKEN_ACCUM.get("input", 0))
        total_output_tokens = tok.get("output", TOKEN_ACCUM.get("output", 0))
    except Exception as exc:
        notify(f"PDF error for {filepath}: {exc}")
        logger.exception("PDF error for %s", filepath)
        duration = time.time() - total_start
        notify(f"Failed {src} after {duration:.2f}s")
        cleanup()
        return pd.DataFrame()

    if result.empty:
        cleanup()
        duration = time.time() - total_start
        notify(f"Finished {src} via LLM with 0 rows in {duration:.2f}s")
        debug_dir = Path(os.getenv("SMART_PRICE_DEBUG_DIR", "LLM_Output_db")) / output_stem
        text_dir = Path(os.getenv("SMART_PRICE_TEXT_DIR", "LLM_Text_db")) / output_stem
        debug_dir.mkdir(parents=True, exist_ok=True)
        text_dir.mkdir(parents=True, exist_ok=True)
        set_output_subdir(None)
        notify("Debug klasörü GitHub'a yükleniyor...")
        logger.info("==> BEGIN upload_debug")
        ok = upload_folder(
            debug_dir,
            remote_prefix=f"LLM_Output_db/{debug_dir.name}",
            file_extensions=[PAGE_IMAGE_EXT],
        )
        logger.info("==> END upload_debug ok=%s", ok)
        if ok:
            notify("Debug klasörü yüklendi")
        else:
            notify("GitHub upload başarısız", "warning")
        return validate_output_df(result)

    if "Para_Birimi" not in result.columns:
        result["Para_Birimi"] = None
    result["Para_Birimi"] = result["Para_Birimi"].apply(normalize_currency)
    result["Para_Birimi"] = result["Para_Birimi"].fillna("₺")
    result["Kaynak_Dosya"] = _basename(filepath, filename)
    result["Yil"] = None
    brand_from_file = detect_brand(_basename(filepath, filename))
    if brand_from_file:
        result["Marka"] = brand_from_file
    else:
        result["Marka"] = result["Açıklama"].apply(detect_brand)
    result["Kategori"] = None
    if "Malzeme_Kodu" not in result.columns:
        result["Malzeme_Kodu"] = None
    if "Kisa_Kod" not in result.columns:
        result["Kisa_Kod"] = None
    if "Ana_Baslik" not in result.columns:
        result["Ana_Baslik"] = None
    if "Alt_Baslik" not in result.columns:
        result["Alt_Baslik"] = None
    if "Sayfa" not in result.columns:
        result["Sayfa"] = 1
    result["Record_Code"] = (
        sanitized_base
        + "|"
        + result["Sayfa"].astype(str)
        + "|"
        + (result.groupby("Sayfa").cumcount() + 1).astype(str)
    )
    result["Image_Path"] = result["Sayfa"].apply(
        lambda page_num: f"LLM_Output_db/{sanitized_base}/page_image_page_{int(page_num):02d}{PAGE_IMAGE_EXT}"
    )
    cols = [
        "Malzeme_Kodu",
        "Açıklama",
        "Kisa_Kod",
        "Fiyat",
        "Para_Birimi",
        "Marka",
        "Kaynak_Dosya",
        "Sayfa",
        "Record_Code",
        "Ana_Baslik",
        "Alt_Baslik",
        "Image_Path",
    ]
    result_df = result[cols].copy()
    duration = time.time() - total_start
    notify(f"Finished {src} via LLM with {len(result_df)} rows in {duration:.2f}s")
    if hasattr(result_df, "__dict__"):
        object.__setattr__(result_df, "page_summary", page_summary)
        object.__setattr__(result_df, "token_counts", {
            "input": total_input_tokens,
            "output": total_output_tokens,
        })
    log_token_counts(src, total_input_tokens, total_output_tokens)
    cleanup()
    debug_dir = Path(os.getenv("SMART_PRICE_DEBUG_DIR", "LLM_Output_db")) / output_stem
    text_dir = Path(os.getenv("SMART_PRICE_TEXT_DIR", "LLM_Text_db")) / output_stem
    debug_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)
    if not any(p.suffix == PAGE_IMAGE_EXT for p in debug_dir.glob(f"*{PAGE_IMAGE_EXT}")):
        try:
            with open(debug_dir / f"page_image_page_01{PAGE_IMAGE_EXT}", "wb") as fh:
                fh.write(b"")
        except Exception:
            pass
    if not any(p.name.startswith("llm_response") for p in text_dir.iterdir()):
        try:
            with open(text_dir / "llm_response_page_01.txt", "w", encoding="utf-8") as fh:
                fh.write("")
        except Exception:
            pass
    set_output_subdir(None)
    notify("Debug klasörü GitHub'a yükleniyor...")
    logger.info("==> BEGIN upload_debug")
    ok = upload_folder(
        debug_dir,
        remote_prefix=f"LLM_Output_db/{debug_dir.name}",
        file_extensions=[PAGE_IMAGE_EXT],
    )
    logger.info("==> END upload_debug ok=%s", ok)
    if ok:
        notify("Debug klasörü yüklendi")
    else:
        notify("GitHub upload başarısız", "warning")
    return validate_output_df(result_df)
