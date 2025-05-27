from __future__ import annotations

import pandas as pd
from typing import Tuple, Optional
from .common_utils import normalize_price, select_latest_year_column

# Possible column headers for product names/codes and prices
POSSIBLE_PRODUCT_NAME_HEADERS = [
    'ürün adı', 'malzeme adı', 'ürün kodu', 'malzeme kodu', 'kod',
    'product name', 'product code', 'material code', 'item name', 'description'
]
POSSIBLE_PRICE_HEADERS = [
    'fiyat', 'birim fiyat', 'liste fiyatı', 'price', 'unit price', 'list price',
    'tutar'
]


def find_columns_in_excel(df: pd.DataFrame) -> Tuple[Optional[str], Optional[str]]:
    """Try to detect product and price columns in an Excel sheet."""
    product_col = price_col = None
    lower_cols = [str(c).lower() for c in df.columns]
    for header in POSSIBLE_PRODUCT_NAME_HEADERS:
        if header in lower_cols:
            product_col = df.columns[lower_cols.index(header)]
            break
    for header in POSSIBLE_PRICE_HEADERS:
        if header in lower_cols:
            price_col = df.columns[lower_cols.index(header)]
            break
    if not price_col:
        # if column names contain years choose the latest
        price_col = select_latest_year_column(df)
    return product_col, price_col


def extract_from_excel(filepath: str) -> pd.DataFrame:
    """Extract product names and prices from an Excel file."""
    all_data = []
    try:
        xls = pd.ExcelFile(filepath)
        for sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet)
            if df.empty:
                continue
            product_col, price_col = find_columns_in_excel(df)
            if product_col and price_col and product_col in df.columns and price_col in df.columns:
                sheet_data = df[[product_col, price_col]].copy()
                sheet_data.columns = ['Malzeme_Adi', 'Fiyat_Ham']
                all_data.append(sheet_data)
    except Exception as exc:
        print(f"Excel error for {filepath}: {exc}")
        return pd.DataFrame()
    if not all_data:
        return pd.DataFrame()
    combined = pd.concat(all_data, ignore_index=True)
    combined['Fiyat'] = combined['Fiyat_Ham'].apply(normalize_price)
    return combined[['Malzeme_Adi', 'Fiyat']].dropna()
