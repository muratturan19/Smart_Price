from __future__ import annotations

import os
import re
import unicodedata
from typing import Tuple, Optional, IO, Any

import pandas as pd
import logging
from datetime import datetime
from pathlib import Path
from .common_utils import (
    normalize_price,
    select_latest_year_column,
    detect_currency,
    detect_brand,
    normalize_currency,
)

logger = logging.getLogger("smart_price")


def _norm_header(text: str) -> str:
    """Normalize a header string for fuzzy matching."""
    text = str(text).replace("_", " ")
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"\s+", " ", text.lower()).strip()
    return text

# Possible column headers for product names/codes and prices
_RAW_CODE_HEADERS = [
    "ürün kodu",
    "urun kodu",
    "malzeme kodu",
    "malzeme",
    "stok kodu",
    "kod",
    "tip",
    "ref no",
    "ref.",
    "ürün ref",
    "ürün tip",
    "product code",
    "part no",
    "item name",
    "item no",
    "item number",
    "item #",
]
_RAW_DESC_HEADERS = [
    "description",
    "ürün açıklaması",
    "açıklama",
    "aciklama",
    "özellikler",
    "detay",
    "explanation",
]

POSSIBLE_CODE_HEADERS = set(_RAW_CODE_HEADERS)
_NORMALIZED_CODE_HEADERS = [_norm_header(h) for h in POSSIBLE_CODE_HEADERS]
POSSIBLE_DESC_HEADERS = [_norm_header(h) for h in _RAW_DESC_HEADERS]

# Short code headers
_RAW_SHORT_HEADERS = [
    'kısa kod',
    'kisa kod',
    'short code',
    'shortcode',
    'kısa ürün kodu',
]
POSSIBLE_SHORT_HEADERS = [_norm_header(h) for h in _RAW_SHORT_HEADERS]

# Combined list used by the PDF extractor
POSSIBLE_PRODUCT_NAME_HEADERS = (
    list(_NORMALIZED_CODE_HEADERS) + POSSIBLE_SHORT_HEADERS + POSSIBLE_DESC_HEADERS
)
_RAW_PRICE_HEADERS = [
    'fiyat', 'birim fiyat', 'liste fiyatı', 'price', 'unit price', 'list price',
    'tutar'
]
_RAW_CURRENCY_HEADERS = ['para birimi', 'currency']

POSSIBLE_PRICE_HEADERS = [_norm_header(h) for h in _RAW_PRICE_HEADERS]
POSSIBLE_CURRENCY_HEADERS = [_norm_header(h) for h in _RAW_CURRENCY_HEADERS]

# Headers for main and sub titles
_RAW_MAIN_HEADERS = ["ana başlık", "ana baslik", "ana_baslik"]
_RAW_SUB_HEADERS = ["alt başlık", "alt baslik", "alt_baslik"]
POSSIBLE_MAIN_HEADERS = [_norm_header(h) for h in _RAW_MAIN_HEADERS]
POSSIBLE_SUB_HEADERS = [_norm_header(h) for h in _RAW_SUB_HEADERS]


def find_columns_in_excel(
    df: pd.DataFrame,
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
    """Try to detect product code, short code, description, price and currency columns."""
    code_col = short_col = desc_col = price_col = currency_col = None
    norm_cols = [_norm_header(c) for c in df.columns]
    used_cols: set[str] = set()
    details: dict[str, tuple[str, str]] = {}

    for header in _NORMALIZED_CODE_HEADERS:
        if header in norm_cols:
            code_col = df.columns[norm_cols.index(header)]
            used_cols.add(code_col)
            details["code"] = (header, code_col)
            break

    for header in POSSIBLE_SHORT_HEADERS:
        if header in norm_cols:
            short_col = df.columns[norm_cols.index(header)]
            used_cols.add(short_col)
            details["short"] = (header, short_col)
            break

    for header in POSSIBLE_DESC_HEADERS:
        if header in norm_cols:
            desc_col = df.columns[norm_cols.index(header)]
            used_cols.add(desc_col)
            details["description"] = (header, desc_col)
            break

    for header in POSSIBLE_PRICE_HEADERS:
        if header in norm_cols:
            price_col = df.columns[norm_cols.index(header)]
            used_cols.add(price_col)
            details["price"] = (header, price_col)
            break

    if not price_col:
        price_col = select_latest_year_column(df)
        if price_col:
            used_cols.add(price_col)
            details["price"] = ("latest_year", price_col)

    for header in POSSIBLE_CURRENCY_HEADERS:
        if header in norm_cols:
            currency_col = df.columns[norm_cols.index(header)]
            used_cols.add(currency_col)
            details["currency"] = (header, currency_col)
            break

    unmatched = [c for c in df.columns if c not in used_cols]
    if details:
        mapped = {
            key: {"header": val[0], "column": val[1]} for key, val in details.items()
        }
    else:
        mapped = {}
    logger.info("excel column mapping %s unmatched %s", mapped, unmatched)

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
    src = _basename(filepath, filename)
    logger.info(f"Processing {src} started at {datetime.now():%Y-%m-%d %H:%M:%S}")
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
            norm_cols = [_norm_header(c) for c in df.columns]
            main_col = None
            sub_col = None
            for header in POSSIBLE_MAIN_HEADERS:
                if header in norm_cols:
                    main_col = df.columns[norm_cols.index(header)]
                    break
            for header in POSSIBLE_SUB_HEADERS:
                if header in norm_cols:
                    sub_col = df.columns[norm_cols.index(header)]
                    break
            if code_col and price_col and price_col in df.columns and code_col in df.columns:
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
                if main_col and main_col in df.columns:
                    cols.append(main_col)
                if sub_col and sub_col in df.columns:
                    cols.append(sub_col)
                sheet_data = df[cols].copy()
                mapping = {}
                if code_col and code_col in df.columns:
                    mapping[code_col] = "Malzeme_Kodu"
                if short_col and short_col in df.columns:
                    mapping[short_col] = "Kisa_Kod"
                if desc_col and desc_col in df.columns:
                    mapping[desc_col] = "Malzeme_Adi"
                else:
                    # If no dedicated description column exists, duplicate the
                    # code column rather than renaming it so both fields are
                    # populated.
                    if code_col and code_col in df.columns:
                        sheet_data["Malzeme_Adi"] = df[code_col]
                mapping[price_col] = "Fiyat_Ham"
                if currency_col and currency_col in df.columns:
                    mapping[currency_col] = "Para_Birimi"
                if main_col and main_col in df.columns:
                    mapping[main_col] = "Ana_Baslik"
                if sub_col and sub_col in df.columns:
                    mapping[sub_col] = "Alt_Baslik"
                sheet_data.rename(columns=mapping, inplace=True)
                if "Para_Birimi" not in sheet_data.columns:
                    sheet_data["Para_Birimi"] = sheet_data["Fiyat_Ham"].astype(str).apply(detect_currency)
                sheet_data["Para_Birimi"] = sheet_data["Para_Birimi"].apply(normalize_currency)
                sheet_data["Para_Birimi"] = sheet_data["Para_Birimi"].fillna("₺")
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
                if "Ana_Baslik" not in sheet_data.columns:
                    sheet_data["Ana_Baslik"] = None
                if "Alt_Baslik" not in sheet_data.columns:
                    sheet_data["Alt_Baslik"] = None
                sheet_data["Sayfa"] = sheet
                all_data.append(sheet_data)
    except Exception:
        logger.exception("Excel error for %s", filepath)
        return pd.DataFrame()
    if not all_data:
        return pd.DataFrame()
    combined = pd.concat(all_data, ignore_index=True)
    logger.debug("[%s] DataFrame oluşturuldu: %d satır", src, len(combined))
    combined["Fiyat"] = combined["Fiyat_Ham"].apply(normalize_price)
    if "Kisa_Kod" not in combined.columns:
        combined["Kisa_Kod"] = None
    if "Malzeme_Kodu" not in combined.columns:
        combined["Malzeme_Kodu"] = None
    if "Ana_Baslik" not in combined.columns:
        combined["Ana_Baslik"] = None
    if "Alt_Baslik" not in combined.columns:
        combined["Alt_Baslik"] = None
    base_name_no_ext = Path(_basename(filepath, filename)).stem
    combined["Record_Code"] = (
        base_name_no_ext
        + "|"
        + combined["Sayfa"].astype(str)
        + "|"
        + (combined.groupby("Sayfa").cumcount() + 1).astype(str)
    )
    combined.rename(columns={"Malzeme_Adi": "Açıklama"}, inplace=True)
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
    ]
    tmp_df = combined[cols].copy()
    before_df = tmp_df.copy()
    drop_mask = tmp_df[["Açıklama", "Fiyat"]].isna().any(axis=1)
    dropped_preview = tmp_df[drop_mask].head().to_dict(orient="records")
    tmp_df.dropna(subset=["Açıklama", "Fiyat"], inplace=True)
    logger.debug(
        "[%s] Filter sonrası: %d satır (drop edilen: %d satır)",
        src,
        len(tmp_df),
        len(before_df) - len(tmp_df),
    )
    if len(before_df) != len(tmp_df):
        logger.debug("[%s] Drop nedeni: subset=['Açıklama', 'Fiyat']", src)
        logger.debug(
            "[%s] Drop edilen ilk 5 satır: %s",
            src,
            dropped_preview,
        )
    if (
        tmp_df.empty
        or "Malzeme_Kodu" not in tmp_df.columns
        or "Fiyat" not in tmp_df.columns
        or tmp_df["Malzeme_Kodu"].isna().all()
        or tmp_df["Fiyat"].isna().all()
    ):
        return pd.DataFrame()
    return tmp_df
