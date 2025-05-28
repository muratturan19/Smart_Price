from __future__ import annotations

import os
import io
import tempfile
from typing import IO, Any, Optional, Sequence
import logging
from datetime import datetime
import difflib
import unicodedata

import pandas as pd
import pdfplumber
import json
import time
from dotenv import load_dotenv

try:
    load_dotenv("../..")
except TypeError:  # pragma: no cover - allow stub without args
    load_dotenv()

# Optional OCR dependencies are imported lazily within extract_from_pdf
import re
from .common_utils import (
    normalize_price,
    detect_currency,
    detect_brand,
    split_code_description,
    gpt_clean_text,
)
from .extract_excel import (
    POSSIBLE_PRICE_HEADERS,
    POSSIBLE_PRODUCT_NAME_HEADERS,
)
from .extract_excel import POSSIBLE_CODE_HEADERS
from . import ocr_llm_fallback

MIN_CODE_RATIO = 0.70
MIN_ROWS_PARSER = 500
CODE_RE = re.compile(r'^([A-ZÇĞİÖŞÜ0-9][A-ZÇĞİÖŞÜ0-9\-/]{1,})', re.I)

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
        logger.info(
            "header_match", extra={"header": cell, "match_type": match_type}
        )
        return True
    return False

_patterns = [
    re.compile(r"^(.*?)\s{2,}([\d\.,]+)\s*(?:TL|TRY|EUR|USD|\$|€)?$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"([A-Z0-9\-\s/]{5,50})\s+([\d\.,]+)\s*(?:TL|TRY|EUR|USD|\$|€)?", re.IGNORECASE),
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
    filepath: str | IO[bytes], *,
    filename: str | None = None,
    log: Any | None = None,
    force_ocr: bool = False,
) -> pd.DataFrame:
    """Extract product information from a PDF file."""
    data = []

    def notify(message: str) -> None:
        logger.info(message)
        if log:
            try:
                log(message)
            except Exception as exc:  # pragma: no cover - log callback errors
                logger.error("log callback failed: %s", exc)

    src = _basename(filepath, filename)
    notify(f"Processing {src} started at {datetime.now():%Y-%m-%d %H:%M:%S}")

    def _llm_extract_from_image(text: str) -> list[dict]:
        """Use a language model to extract product names and prices from OCR text."""
        # pragma: no cover - not exercised in tests
        notify("LLM fazı başladı")
        # Environment already loaded at module import time
        pass
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

        model_name = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        excerpt = text[:200].replace("\n", " ")
        logger.debug("Using model %s on text excerpt: %r", model_name, excerpt)

        prompt = f"""
            Aşağıda bir fiyat listesi metni var. Bu metinden sadece ürün adı ve fiyat bilgilerini içeren
            bir JSON dizisi üret. Her öğe şu anahtarları içermeli:
            - 'Malzeme_Adı': Ürünün adı veya açıklaması
            - 'Fiyat': Sayısal fiyat değeri
            - 'Para_Birimi': Fiyatın para birimi (örn: TL, USD)
            
            Lütfen sadece geçerli ürünleri al ve gereksiz satırları atla. Sadece geçerli JSON döndür.
            return only valid JSON.
            
            Metin:
            {text}
            """

        logger.debug("LLM prompt length: %d", len(prompt))
        logger.debug("LLM prompt excerpt: %r", prompt[:200])


        try:
            resp = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            time.sleep(0.5)
            content = resp.choices[0].message.content
            logger.debug("LLM raw response: %r", content.strip()[:200])
            try:
                cleaned = gpt_clean_text(content)
                items = json.loads(cleaned)
                logger.debug("First parsed items: %r", items[:2])
                if not items:
                    excerpt = text[:100].replace("\n", " ")
                    notify(
                        f"no items parsed by {model_name}; OCR text excerpt: {excerpt!r}"
                    )
                    return []
            except json.JSONDecodeError:
                notify(f"LLM returned invalid JSON: {content!r}")
                notify("LLM returned no data")
                return []
        except Exception as exc:
            notify(f"openai request failed: {exc}")
            notify("LLM returned no data")
            return []

        results = []
        for item in items:
            name = str(item.get("name") or item.get("product") or "").strip()
            price_raw = str(item.get("price", "")).strip()
            val = normalize_price(price_raw)
            if name and val is not None:
                results.append(
                    {
                        "Malzeme_Adi": name,
                        "Fiyat": val,
                        "Para_Birimi": detect_currency(price_raw),
                    }
                )
        count = len(results)
        if count:
            notify(f"LLM parsed {count} items")
        else:
            notify("LLM returned no data")
        return results

    notify("1. faz")
    tmp_for_ocr: str | None = None
    def cleanup() -> None:
        if tmp_for_ocr:
            try:
                os.remove(tmp_for_ocr)
            except Exception as exc:
                notify(f"temp file cleanup failed: {exc}")
    page_range = None
    try:
        if isinstance(filepath, (str, bytes, os.PathLike)):
            cm = pdfplumber.open(filepath)
            path_for_ocr = filepath
        else:
            try:
                filepath.seek(0)
            except Exception as exc:
                notify(f"seek failed: {exc}")
            pdf_bytes = filepath.read()
            cm = pdfplumber.open(io.BytesIO(pdf_bytes))
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            tmp.write(pdf_bytes)
            tmp.close()
            tmp_for_ocr = tmp.name
            path_for_ocr = tmp_for_ocr
        with cm as pdf:
            page_range = range(1, len(pdf.pages) + 1)
            if force_ocr:
                notify("Force OCR/LLM enabled")
                result = ocr_llm_fallback.parse(path_for_ocr, page_range)
                cleanup()
                return result
            for page in pdf.pages:
                text = page.extract_text() or ""
                notify(
                    f"Page {page.page_number} read with {len(text.splitlines())} lines"
                )
                if text:
                    for line in text.split("\n"):
                        line = line.strip()
                        if len(line) < 5:
                            continue
                        for pattern in _patterns:
                            matches = pattern.findall(line)
                            if not matches:
                                m = pattern.match(line)
                                if m:
                                    matches = [m.groups()]
                            for match in matches:
                                if len(match) != 2:
                                    continue
                                product_name = re.sub(r"\s{2,}", " ", match[0].strip())
                                price_raw = match[1]
                                price = normalize_price(price_raw)
                                if product_name and price is not None:
                                    data.append(
                                        {
                                            "Malzeme_Adi": product_name,
                                            "Fiyat": price,
                                            "Para_Birimi": detect_currency(price_raw),
                                            "Sayfa": page.page_number,
                                        }
                                    )
                                    notify(
                                        f"Matched on page {page.page_number}: {line[:100]}"
                                    )

                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue
                    try:
                        header_row = None
                        if table and any(
                            header_match(
                                c,
                                POSSIBLE_PRODUCT_NAME_HEADERS,
                                match_type="DESC",
                            )
                            or header_match(
                                c,
                                POSSIBLE_PRICE_HEADERS,
                                match_type="PRICE",
                            )
                            for c in table[0]
                        ):
                            header_row = [str(c or "").strip() for c in table[0]]
                            df_table = pd.DataFrame(table[1:], columns=header_row)
                        else:
                            df_table = pd.DataFrame(table)

                        df_table.dropna(how="all", inplace=True)

                        product_idx = 0
                        price_idx = -1
                        if any(
                            header_match(
                                c,
                                POSSIBLE_PRODUCT_NAME_HEADERS,
                                match_type="DESC",
                            )
                            for c in df_table.columns
                        ):
                            product_idx = [
                                i
                                for i, c in enumerate(df_table.columns)
                                if header_match(
                                    c,
                                    POSSIBLE_PRODUCT_NAME_HEADERS,
                                    match_type="DESC",
                                )
                            ][0]
                        if any(
                            header_match(
                                c,
                                POSSIBLE_PRICE_HEADERS,
                                match_type="PRICE",
                            )
                            for c in df_table.columns
                        ):
                            price_idx = [
                                i
                                for i, c in enumerate(df_table.columns)
                                if header_match(
                                    c,
                                    POSSIBLE_PRICE_HEADERS,
                                    match_type="PRICE",
                                )
                            ][0]

                        for _, row in df_table.iterrows():
                            if len(row) <= max(product_idx, abs(price_idx)):
                                continue
                            first = (row[0] or "").strip()
                            code = CODE_RE.match(first)
                            if code and not header_match(
                                first,
                                POSSIBLE_CODE_HEADERS,
                                match_type="CODE",
                            ):
                                code_val = code.group(1)
                            else:
                                code_val = None

                            product = str(row.iloc[product_idx]).strip()
                            price_raw = str(row.iloc[price_idx]).strip()
                            if product and price_raw:
                                price = normalize_price(price_raw)
                                if pd.isna(code_val) or pd.isna(price):
                                    logger.warning(
                                        "Empty field p%s: %s",
                                        page.page_number,
                                        str(row)[:80],
                                    )
                                if price is not None:
                                    data.append(
                                        {
                                            "Malzeme_Adi": product,
                                            "Fiyat": price,
                                            "Para_Birimi": detect_currency(price_raw),
                                            "Sayfa": page.page_number,
                                            "Malzeme_Kodu": code_val,
                                        }
                                    )
                    except Exception as exc:
                        notify(f"table parse error: {exc}")
                        continue

        phase1_count = len(data)
        if phase1_count:
            notify(f"Phase 1 parsed {phase1_count} items; skipping OCR/LLM")
        if not data:
            try:
                from pdf2image import convert_from_path  # type: ignore
                import pytesseract  # type: ignore
            except Exception as exc:
                notify(f"OCR libraries unavailable: {exc}")
            else:
                notify("OCR faz\u0131 başladı")
                images = convert_from_path(path_for_ocr)
                ocr_text = "\n".join(pytesseract.image_to_string(img) for img in images)
                logger.debug("OCR text excerpt: %r", ocr_text[:200])
                llm_data = _llm_extract_from_image(ocr_text)
                if llm_data:
                    notify(f"LLM parsed {len(llm_data)} items")
                    for entry in llm_data:
                        data.append(entry)
                else:
                    notify("LLM returned no data")
    except Exception as exc:
        notify(f"PDF error for {filepath}: {exc}")
        logger.exception("PDF error for %s", filepath)
        cleanup()
        return pd.DataFrame()
    if not data:
        cleanup()
        return pd.DataFrame()
    df = pd.DataFrame(data)
    if not df.empty:
        codes, descs = zip(*df["Malzeme_Adi"].map(split_code_description))
        df["Malzeme_Adi"] = list(descs)
        if "Malzeme_Kodu" in df.columns:
            df["Malzeme_Kodu"] = df["Malzeme_Kodu"].fillna(pd.Series(codes))
        else:
            df["Malzeme_Kodu"] = list(codes)

    code_filled = df["Malzeme_Kodu"].notna().sum()
    rows_extracted = len(df)
    if rows_extracted < MIN_ROWS_PARSER or (
        rows_extracted and code_filled / rows_extracted < MIN_CODE_RATIO
    ):
        logger.warning("Low-quality Phase-1 parse \u2192 switching to OCR+LLM")
        result = ocr_llm_fallback.parse(path_for_ocr, page_range)
        cleanup()
        return result
    # Default to Turkish Lira if currency could not be determined
    df["Para_Birimi"] = df["Para_Birimi"].fillna("TL")
    df["Kaynak_Dosya"] = _basename(filepath, filename)
    df["Yil"] = None
    brand_from_file = detect_brand(_basename(filepath, filename))
    if brand_from_file:
        df["Marka"] = brand_from_file
    else:
        df["Marka"] = df["Malzeme_Adi"].apply(detect_brand)
    df["Kategori"] = None
    if "Kisa_Kod" not in df.columns:
        df["Kisa_Kod"] = None
    df.rename(columns={"Malzeme_Adi": "Descriptions"}, inplace=True)
    cols = [
        "Malzeme_Kodu",
        "Descriptions",
        "Kisa_Kod",
        "Fiyat",
        "Para_Birimi",
        "Marka",
        "Kaynak_Dosya",
    ]
    result_df = df[cols].dropna(subset=["Descriptions", "Fiyat"])
    notify(f"Finished {src} with {len(result_df)} items")
    cleanup()
    return result_df
