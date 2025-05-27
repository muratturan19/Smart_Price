from __future__ import annotations

import pandas as pd
from typing import Tuple, Optional
from .common_utils import normalize_price, select_latest_year_column

# Possible column headers for product names/codes and prices
POSSIBLE_CODE_HEADERS = [
    'ürün kodu', 'malzeme kodu', 'kod', 'product code',
    'material code', 'item code', 'code'
]
POSSIBLE_DESC_HEADERS = [
    'ürün adı', 'malzeme adı', 'product name', 'item name', 'description'
]

# Combined list used by the PDF extractor
POSSIBLE_PRODUCT_NAME_HEADERS = POSSIBLE_CODE_HEADERS + POSSIBLE_DESC_HEADERS
POSSIBLE_PRICE_HEADERS = [
    'fiyat', 'birim fiyat', 'liste fiyatı', 'price', 'unit price', 'list price',
    'tutar'
]
POSSIBLE_CURRENCY_HEADERS = ['para birimi', 'currency']


def find_columns_in_excel(
    df: pd.DataFrame,
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """Try to detect product code, description, price and currency columns."""
    code_col = desc_col = price_col = currency_col = None
    lower_cols = [str(c).lower() for c in df.columns]

    for header in POSSIBLE_CODE_HEADERS:
        if header in lower_cols:
            code_col = df.columns[lower_cols.index(header)]
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

    return code_col, desc_col, price_col, currency_col


def extract_from_excel(filepath: str) -> pd.DataFrame:
    """Extract product names and prices from an Excel file."""
    all_data = []
    try:
        xls = pd.ExcelFile(filepath)
        for sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet)
            if df.empty:
                continue
            code_col, desc_col, price_col, currency_col = find_columns_in_excel(df)
            if (desc_col or code_col) and price_col and price_col in df.columns:
                cols = []
                if code_col and code_col in df.columns:
                    cols.append(code_col)
                if desc_col and desc_col in df.columns:
                    cols.append(desc_col)
                cols.append(price_col)
                if currency_col and currency_col in df.columns:
                    cols.append(currency_col)
                sheet_data = df[cols].copy()
                mapping = {}
                if code_col and code_col in df.columns:
                    mapping[code_col] = 'Malzeme_Kodu'
                if desc_col and desc_col in df.columns:
                    mapping[desc_col] = 'Malzeme_Adi'
                elif code_col and code_col in df.columns and 'Malzeme_Adi' not in mapping.values():
                    mapping[code_col] = 'Malzeme_Adi'
                mapping[price_col] = 'Fiyat_Ham'
                if currency_col and currency_col in df.columns:
                    mapping[currency_col] = 'Para_Birimi'
                sheet_data.rename(columns=mapping, inplace=True)
                if 'Para_Birimi' not in sheet_data.columns:
                    sheet_data['Para_Birimi'] = '€'
                all_data.append(sheet_data)
    except Exception as exc:
        print(f"Excel error for {filepath}: {exc}")
        return pd.DataFrame()
    if not all_data:
        return pd.DataFrame()
    combined = pd.concat(all_data, ignore_index=True)
    combined['Fiyat'] = combined['Fiyat_Ham'].apply(normalize_price)
    return combined[['Malzeme_Adi', 'Fiyat']].dropna()
