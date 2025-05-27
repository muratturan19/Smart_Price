from __future__ import annotations

import pandas as pd
import pdfplumber
import re
from .common_utils import normalize_price
from .extract_excel import POSSIBLE_PRICE_HEADERS, POSSIBLE_PRODUCT_NAME_HEADERS

_patterns = [
    re.compile(r"^(.*?)\s{2,}([\d\.,]+)\s*(?:TL|TRY|EUR|USD|\$|€)?$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"([A-Z0-9\-\s/]{5,50})\s+([\d\.,]+)\s*(?:TL|TRY|EUR|USD|\$|€)?", re.IGNORECASE),
    re.compile(r"Item Code:\s*(.*?)\s*Price:\s*([\d\.,]+)", re.IGNORECASE),
    re.compile(r"Ürün No:\s*(.*?)\s*Birim Fiyat:\s*([\d\.,]+)", re.IGNORECASE),
]


def extract_from_pdf(filepath: str) -> pd.DataFrame:
    """Extract product information from a PDF file."""
    data = []
    try:
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    tables = page.extract_tables()
                    for table in tables:
                        if not table:
                            continue
                        try:
                            df_table = pd.DataFrame(table)
                            df_table.dropna(how='all', inplace=True)
                            product_idx = 0
                            price_idx = -1
                            if any(str(c).lower() in POSSIBLE_PRODUCT_NAME_HEADERS for c in df_table.columns):
                                product_idx = [i for i,c in enumerate(df_table.columns) if str(c).lower() in POSSIBLE_PRODUCT_NAME_HEADERS][0]
                            if any(str(c).lower() in POSSIBLE_PRICE_HEADERS for c in df_table.columns):
                                price_idx = [i for i,c in enumerate(df_table.columns) if str(c).lower() in POSSIBLE_PRICE_HEADERS][0]
                            for _, row in df_table.iterrows():
                                if len(row) <= max(product_idx, abs(price_idx)):
                                    continue
                                product = str(row.iloc[product_idx]).strip()
                                price = str(row.iloc[price_idx]).strip()
                                if product and price:
                                    val = normalize_price(price)
                                    if val is not None:
                                        data.append({'Malzeme_Adi': product, 'Fiyat': val})
                        except Exception:
                            continue
                    continue
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
                            price = normalize_price(match[1])
                            if product_name and price is not None:
                                data.append({'Malzeme_Adi': product_name, 'Fiyat': price})
    except Exception as exc:
        print(f"PDF error for {filepath}: {exc}")
        return pd.DataFrame()
    return pd.DataFrame(data)
