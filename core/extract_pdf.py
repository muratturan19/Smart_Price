from __future__ import annotations

import os
import io
import tempfile
from typing import IO, Any, Optional

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
        if log:
            try:
                log(message)
            except Exception as exc:  # pragma: no cover - log callback errors
                print(f"log callback failed: {exc}")
        else:
            print(message)

    def _llm_extract_from_image(text: str) -> list[dict]:
        """Use GPT-3.5 to extract product names and prices from OCR text."""
        # pragma: no cover - not exercised in tests
        try:
            from dotenv import load_dotenv  # type: ignore
            load_dotenv()
        except Exception as exc:  # pragma: no cover - optional dep missing
            notify(f"dotenv load failed: {exc}")

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or not text:
            return []

        try:
            import openai  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dep missing
            notify(f"openai import failed: {exc}")
            return []

        client = openai.OpenAI(api_key=api_key)  # type: ignore[attr-defined]

        prompt = (
            "Extract product names and prices from the text below "
            "and return a JSON array of objects with 'name' and 'price' keys.\n"
            f"Text:\n{text}"
        )

        try:
            resp = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            time.sleep(0.5)
            content = resp.choices[0].message.content
            try:
                cleaned = gpt_clean_text(content)
                items = json.loads(cleaned)
            except json.JSONDecodeError:
                notify(f"LLM returned invalid JSON: {content!r}")
                return []
        except Exception as exc:
            notify(f"openai request failed: {exc}")
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
                page_added = False
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
                                    page_added = True

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
                                    page_added = True
                    except Exception as exc:
                        notify(f"table parse error: {exc}")
                        continue

                if not page_added:
                    try:
                        from pdf2image import convert_from_path  # type: ignore
                        import pytesseract  # type: ignore
                    except Exception as exc:
                        notify(f"OCR libraries unavailable: {exc}")
                        continue
                    notify("OCR faz\u0131")
                    images = convert_from_path(
                        path_for_ocr,
                        first_page=page.page_number,
                        last_page=page.page_number,
                    )
                    llm_text = []
                    for img in images:
                        ocr_text = pytesseract.image_to_string(img)
                        llm_text.append(ocr_text)
                        notify(ocr_text)
                        for line in ocr_text.split("\n"):
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
                                        page_added = True
                    if not page_added:
                        notify("LLM faz\u0131")
                        llm_data = _llm_extract_from_image("\n".join(llm_text))
                        count = len(llm_data)
                        if count:
                            notify(f"LLM parsed {count} items")
                            for entry in llm_data:
                                entry.setdefault("Sayfa", page.page_number)
                                data.append(entry)
                        else:
                            notify("LLM returned no data")
                        page_added = bool(llm_data)
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
