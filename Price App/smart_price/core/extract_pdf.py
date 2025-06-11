from __future__ import annotations

import os
import tempfile
from typing import IO, Any, Optional, Sequence, Callable, List
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

MIN_CODE_RATIO = 0.70
MIN_ROWS_PARSER = 500
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
) -> pd.DataFrame:
    """Extract product information from a PDF file."""
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

    rows: list[dict[str, object]] = []
    phase1_df: pd.DataFrame | None = None
    try:
        import pdfplumber  # type: ignore
    except Exception:
        pdfplumber = None  # type: ignore

    if pdfplumber is not None:
        try:
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    for line in text.splitlines():
                        parts = line.split()
                        if len(parts) >= 2:
                            price_val = normalize_price(parts[-1])
                            if price_val is None:
                                continue
                            rows.append(
                                {
                                    "Açıklama": " ".join(parts[:-1]),
                                    "Fiyat": price_val,
                                    "Para_Birimi": normalize_currency(
                                        detect_currency(parts[-1])
                                    ),
                                    "Sayfa": getattr(page, "page_number", 1),
                                }
                            )
                    for table in page.extract_tables() or []:
                        if not table or len(table) <= 1:
                            continue
                        hdr = [str(h or "").strip() for h in table[0]]
                        for row in table[1:]:
                            if len(row) != len(hdr):
                                continue
                            data = dict(zip(hdr, row))
                            descr = str(data.get("Ürün Adı") or data.get("Ürün") or "").strip()
                            price_raw = str(data.get("Fiyat", "")).strip()
                            price_val = normalize_price(price_raw)
                            if descr and price_val is not None:
                                rows.append(
                                    {
                                        "Açıklama": descr,
                                        "Fiyat": price_val,
                                        "Para_Birimi": normalize_currency(
                                            detect_currency(price_raw)
                                        ),
                                        "Sayfa": getattr(page, "page_number", 1),
                                    }
                                )
        except Exception as exc:
            logger.error("pdfplumber failed: %s", exc)

    if rows:
        df = pd.DataFrame(rows)
        df["Malzeme_Kodu"] = None
        df["Kisa_Kod"] = None
        df["Marka"] = None
        df["Kaynak_Dosya"] = _basename(filepath, filename)
        df["Record_Code"] = None
        df["Ana_Baslik"] = None
        df["Alt_Baslik"] = None
        df["Image_Path"] = None
        df["Para_Birimi"] = df["Para_Birimi"].fillna("₺")
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
        df = df.reindex(columns=cols, fill_value=None)
        notify(f"Phase 1 parsed {len(df)} rows")
        phase1_df = df
        if len(phase1_df) >= MIN_ROWS_PARSER:
            duration = time.time() - total_start
            notify(
                f"Finished {src} via pdfplumber with {len(phase1_df)} rows"
                f" (>= {MIN_ROWS_PARSER})"
            )
            set_output_subdir(None)
            return validate_output_df(phase1_df)

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

        client = OpenAI(api_key=api_key)

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
        try:
            result = ocr_llm_fallback.parse(
                path_for_llm,
                output_name=output_stem if tmp_for_llm else None,
                prompt=guide_prompt,
            )
        except TypeError:
            # Support older parse() signatures used in tests
            result = ocr_llm_fallback.parse(path_for_llm)
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

    if result.empty and phase1_df is not None:
        result = phase1_df
        notify(f"Finished {src} via pdfplumber with {len(result)} rows")
    elif result.empty:
        cleanup()
        duration = time.time() - total_start
        notify(f"Finished {src} via LLM with 0 rows in {duration:.2f}s")
        debug_dir = (
            Path(os.getenv("SMART_PRICE_DEBUG_DIR", "LLM_Output_db")) / output_stem
        )
        set_output_subdir(None)
        notify("Debug klasörü GitHub'a yükleniyor...")
        ok = upload_folder(debug_dir, remote_prefix=f"LLM_Output_db/{debug_dir.name}")
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
        lambda page_num: f"LLM_Output_db/{sanitized_base}/page_image_page_{int(page_num):02d}.png"
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
    debug_dir.mkdir(parents=True, exist_ok=True)
    if not any(p.suffix == ".png" for p in debug_dir.glob("*.png")):
        try:
            with open(debug_dir / "page_image_page_01.png", "wb") as fh:
                fh.write(b"")
        except Exception:
            pass
    if not any(p.name.startswith("llm_response") for p in debug_dir.iterdir()):
        try:
            with open(debug_dir / "llm_response_page_01.txt", "w", encoding="utf-8") as fh:
                fh.write("")
        except Exception:
            pass
    set_output_subdir(None)
    notify("Debug klasörü GitHub'a yükleniyor...")
    ok = upload_folder(debug_dir, remote_prefix=f"LLM_Output_db/{debug_dir.name}")
    if ok:
        notify("Debug klasörü yüklendi")
    else:
        notify("GitHub upload başarısız", "warning")
    return validate_output_df(result_df)
