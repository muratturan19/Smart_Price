"""Helpers for parsing DataFrame objects."""

from __future__ import annotations

import pandas as pd
import re

from .core.extract_excel import find_columns_in_excel
from .core.common_utils import (
    normalize_price,
    detect_currency,
    detect_brand,
)


def parse_df(df: pd.DataFrame) -> pd.DataFrame:
    """Parse a DataFrame in the same fashion as :func:`extract_from_excel`.

    The function attempts to detect product code, description and price columns
    using :func:`smart_price.core.extract_excel.find_columns_in_excel` and then
    returns a DataFrame with the standard columns used across the library.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    code_col, short_col, desc_col, price_col, currency_col = find_columns_in_excel(df)

    if not (price_col and (desc_col or code_col) and price_col in df.columns):
        return pd.DataFrame()

    cols: list[str] = []
    if code_col and code_col in df.columns:
        cols.append(code_col)
    if short_col and short_col in df.columns:
        cols.append(short_col)
    if desc_col and desc_col in df.columns:
        cols.append(desc_col)
    cols.append(price_col)
    if currency_col and currency_col in df.columns:
        cols.append(currency_col)

    data = df[cols].copy()

    mapping = {}
    if code_col and code_col in df.columns:
        mapping[code_col] = "Malzeme_Kodu"
    if short_col and short_col in df.columns:
        mapping[short_col] = "Kisa_Kod"
    if desc_col and desc_col in df.columns:
        mapping[desc_col] = "Malzeme_Adi"
    else:
        if code_col and code_col in df.columns:
            data["Malzeme_Adi"] = df[code_col]
    mapping[price_col] = "Fiyat_Ham"
    if currency_col and currency_col in df.columns:
        mapping[currency_col] = "Para_Birimi"
    data.rename(columns=mapping, inplace=True)

    if "Para_Birimi" not in data.columns:
        data["Para_Birimi"] = data["Fiyat_Ham"].astype(str).apply(detect_currency)
    data["Para_Birimi"] = data["Para_Birimi"].fillna("TL")

    year_match = None
    if price_col:
        year_match = re.search(r"(\d{4})", str(price_col))
    data["Yil"] = int(year_match.group(1)) if year_match else None

    data["Kaynak_Dosya"] = None
    data["Marka"] = data["Malzeme_Adi"].astype(str).apply(detect_brand)
    data["Kategori"] = None
    data["Sayfa"] = None

    result = data.copy()
    result["Fiyat"] = result["Fiyat_Ham"].apply(normalize_price)
    if "Kisa_Kod" not in result.columns:
        result["Kisa_Kod"] = None
    if "Malzeme_Kodu" not in result.columns:
        result["Malzeme_Kodu"] = None
    result["Record_Code"] = None
    result.rename(columns={"Malzeme_Adi": "Descriptions"}, inplace=True)
    cols_out = [
        "Malzeme_Kodu",
        "Descriptions",
        "Kisa_Kod",
        "Fiyat",
        "Para_Birimi",
        "Marka",
        "Kaynak_Dosya",
        "Record_Code",
    ]
    return result[cols_out].dropna(subset=["Descriptions", "Fiyat"])

