from __future__ import annotations

import os
import io
import tempfile
from typing import IO, Any, Optional
import logging
from datetime import datetime

import pandas as pd
import pdfplumber
import json
import time

# Optional OCR dependencies are imported lazily within extract_from_pdf
import re
from .common_utils import (
    normalize_price,
    detect_currency,
    detect_brand,
    split_code_description,
    gpt_clean_text,
)
from .extract_excel import POSSIBLE_PRICE_HEADERS, POSSIBLE_PRODUCT_NAME_HEADERS

logger = logging.getLogger("smart_price")

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
    filepath: str | IO[bytes], *, filename: str | None = None, log: Any | None = None
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
        try:
            from dotenv import load_dotenv  # type: ignore
            load_dotenv()
        except Exception as exc:  # pragma: no cover - optional dep missing
            notify(f"dotenv load failed: {exc}")

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or not text:
            notify("LLM returned no data")
            return []

        try:
            import openai  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dep missing
            notify(f"openai import failed: {exc}")
            notify("LLM returned no data")
            return []

        client = openai.OpenAI(api_key=api_key)  # type: ignore[attr-defined]

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
            for page in pdf.pages:
                text = page.extract_text() or ""
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

                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue
                    try:
                        header_row = None
                        if table and any(
                            str(c or "").strip().lower() in POSSIBLE_PRODUCT_NAME_HEADERS
                            or str(c or "").strip().lower() in POSSIBLE_PRICE_HEADERS
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
                            str(c).lower() in POSSIBLE_PRODUCT_NAME_HEADERS
                            for c in df_table.columns
                        ):
                            product_idx = [
                                i
                                for i, c in enumerate(df_table.columns)
                                if str(c).lower() in POSSIBLE_PRODUCT_NAME_HEADERS
                            ][0]
                        if any(
                            str(c).lower() in POSSIBLE_PRICE_HEADERS
                            for c in df_table.columns
                        ):
                            price_idx = [
                                i
                                for i, c in enumerate(df_table.columns)
                                if str(c).lower() in POSSIBLE_PRICE_HEADERS
                            ][0]

                        for _, row in df_table.iterrows():
                            if len(row) <= max(product_idx, abs(price_idx)):
                                continue
                            product = str(row.iloc[product_idx]).strip()
                            price_raw = str(row.iloc[price_idx]).strip()
                            if product and price_raw:
                                val = normalize_price(price_raw)
                                if val is not None:
                                    data.append(
                                        {
                                            "Malzeme_Adi": product,
                                            "Fiyat": val,
                                            "Para_Birimi": detect_currency(price_raw),
                                            "Sayfa": page.page_number,
                                        }
                                    )
                    except Exception as exc:
                        notify(f"table parse error: {exc}")
                        continue

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
                llm_data = _llm_extract_from_image(ocr_text)
                if llm_data:
                    notify(f"LLM parsed {len(llm_data)} items")
                    for entry in llm_data:
                        data.append(entry)
                else:
                    notify("LLM returned no data")
    except Exception as exc:
        notify(f"PDF error for {filepath}: {exc}")
        return pd.DataFrame()
    finally:
        if tmp_for_ocr:
            try:
                os.remove(tmp_for_ocr)
            except Exception as exc:
                notify(f"temp file cleanup failed: {exc}")
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    if not df.empty:
        codes, descs = zip(*df["Malzeme_Adi"].map(split_code_description))
        df["Malzeme_Kodu"] = list(codes)
        df["Malzeme_Adi"] = list(descs)
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
    return df[cols].dropna(subset=["Descriptions", "Fiyat"])
