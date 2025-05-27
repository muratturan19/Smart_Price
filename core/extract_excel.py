from __future__ import annotations

import os
import re
from typing import Tuple, Optional, IO, Any

import pandas as pd
from .common_utils import (
    normalize_price,
    select_latest_year_column,
    detect_currency,
    detect_brand,
)

# Possible column headers for product names/codes and prices
POSSIBLE_CODE_HEADERS = [
    'ürün kodu',
    'malzeme kodu',
    'kod',
    'product code',
    'material code',
    'item code',
    'code',
    'ürün numarası',
    'item no',
    'product no',
    'malzeme adı',
    'malzeme',
    'ürün',
    'product name',
    'name',
]
POSSIBLE_DESC_HEADERS = [
    'ürün adı',
    'item name',
    'description',
    'ürün açıklaması',
    'açıklama',
]

# Short code headers
POSSIBLE_SHORT_HEADERS = [
    'kısa kod',
    'kisa kod',
    'short code',
    'shortcode',
    'kısa ürün kodu',
]

# Combined list used by the PDF extractor
POSSIBLE_PRODUCT_NAME_HEADERS = (
    POSSIBLE_CODE_HEADERS + POSSIBLE_SHORT_HEADERS + POSSIBLE_DESC_HEADERS
)
POSSIBLE_PRICE_HEADERS = [
    'fiyat', 'birim fiyat', 'liste fiyatı', 'price', 'unit price', 'list price',
    'tutar'
]
POSSIBLE_CURRENCY_HEADERS = ['para birimi', 'currency']


def find_columns_in_excel(
    df: pd.DataFrame,
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
    """Try to detect product code, short code, description, price and currency columns."""
    code_col = short_col = desc_col = price_col = currency_col = None
    lower_cols = [str(c).lower() for c in df.columns]

    for header in POSSIBLE_CODE_HEADERS:
        if header in lower_cols:
            code_col = df.columns[lower_cols.index(header)]
            break

    for header in POSSIBLE_SHORT_HEADERS:
        if header in lower_cols:
            short_col = df.columns[lower_cols.index(header)]
            break

    for header in POSSIBLE_DESC_HEADERS:
        if header in lower_cols:
            desc_col = df.columns[lower_cols.index(header)]
            break

    for header in POSSIBLE_PRICE_HEADERS:
        if header in lower_cols:
            price_col = df.columns[lower_cols.index(header)]
            break

    if not price_col:
        price_col = select_latest_year_column(df)

    for header in POSSIBLE_CURRENCY_HEADERS:
        if header in lower_cols:
            currency_col = df.columns[lower_cols.index(header)]
            break

    return code_col, short_col, desc_col, price_col, currency_col


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


def extract_from_excel(
    filepath: str | IO[bytes], *, filename: str | None = None
) -> pd.DataFrame:
    """Extract product information from an Excel file."""
    all_data = []
    try:
        ext = os.path.splitext(filename or _basename(filepath))[1].lower()
        engine = "openpyxl"
        if ext == ".xls":
            engine = "xlrd"
        xls = pd.ExcelFile(filepath, engine=engine)
        for sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet, engine=engine)
            if df.empty:
                continue
            code_col, short_col, desc_col, price_col, currency_col = find_columns_in_excel(df)
            if (desc_col or code_col) and price_col and price_col in df.columns:
                cols = []
                if code_col and code_col in df.columns:
                    cols.append(code_col)
                if short_col and short_col in df.columns:
                    cols.append(short_col)
                if desc_col and desc_col in df.columns:
                    cols.append(desc_col)
                cols.append(price_col)
                if currency_col and currency_col in df.columns:
                    cols.append(currency_col)
                sheet_data = df[cols].copy()
                mapping = {}
                if code_col and code_col in df.columns:
                    mapping[code_col] = "Malzeme_Kodu"
                if short_col and short_col in df.columns:
                    mapping[short_col] = "Kisa_Kod"
                if desc_col and desc_col in df.columns:
                    mapping[desc_col] = "Malzeme_Adi"
                elif code_col and code_col in df.columns and "Malzeme_Adi" not in mapping.values():
                    mapping[code_col] = "Malzeme_Adi"
                mapping[price_col] = "Fiyat_Ham"
                if currency_col and currency_col in df.columns:
                    mapping[currency_col] = "Para_Birimi"
                sheet_data.rename(columns=mapping, inplace=True)
                if "Para_Birimi" not in sheet_data.columns:
                    sheet_data["Para_Birimi"] = sheet_data["Fiyat_Ham"].astype(str).apply(detect_currency)
                # Default to Turkish Lira if currency could not be determined
                sheet_data["Para_Birimi"] = sheet_data["Para_Birimi"].fillna("TL")
                sheet_data["Kaynak_Dosya"] = _basename(filepath, filename)
                brand_from_file = detect_brand(_basename(filepath, filename))
                year_match = None
                if price_col:
                    year_match = re.search(r"(\d{4})", str(price_col))
                sheet_data["Yil"] = int(year_match.group(1)) if year_match else None
                if brand_from_file:
                    sheet_data["Marka"] = brand_from_file
                else:
                    sheet_data["Marka"] = sheet_data["Malzeme_Adi"].astype(str).apply(detect_brand)
                sheet_data["Kategori"] = None
                sheet_data["Sayfa"] = sheet
                all_data.append(sheet_data)
    except Exception as exc:
        print(f"Excel error for {filepath}: {exc}")
        return pd.DataFrame()
    if not all_data:
        return pd.DataFrame()
    combined = pd.concat(all_data, ignore_index=True)
    combined["Fiyat"] = combined["Fiyat_Ham"].apply(normalize_price)
    if "Kisa_Kod" not in combined.columns:
        combined["Kisa_Kod"] = None
    if "Malzeme_Kodu" not in combined.columns:
        combined["Malzeme_Kodu"] = None
    combined.rename(columns={"Malzeme_Adi": "Descriptions"}, inplace=True)
    cols = [
        "Malzeme_Kodu",
        "Descriptions",
        "Kisa_Kod",
        "Fiyat",
        "Para_Birimi",
        "Marka",
        "Kaynak_Dosya",
    ]
    return combined[cols].dropna(subset=["Descriptions", "Fiyat"])
