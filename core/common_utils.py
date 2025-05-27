import re
from typing import Optional


def normalize_price(price_str: Optional[str]) -> Optional[float]:
    """Convert a raw price string to a float value.

    Parameters
    ----------
    price_str : str or Any
        String representation of the price. Currency symbols and thousand
        separators are allowed.

    Returns
    -------
    float or None
        Parsed price as a ``float`` if successful, otherwise ``None``.
    """
    if price_str is None:
        return None
    price_str = str(price_str).strip()
    price_str = re.sub(r"[^\d,\.]", "", price_str)
    if "," in price_str and "." in price_str:
        if price_str.rfind(".") < price_str.rfind(","):
            price_str = price_str.replace(".", "").replace(",", ".")
    elif "," in price_str:
        price_str = price_str.replace(",", ".")
    try:
        return float(price_str)
    except ValueError:
        return None


def detect_currency(text: str) -> Optional[str]:
    """Try to guess the currency from a text snippet."""
    if not text:
        return None
    text = text.upper()
    if "EUR" in text or "€" in text:
        return "EUR"
    if "USD" in text or "$" in text:
        return "USD"
    if "TL" in text or "TRY" in text:
        return "TRY"
    return None


def select_latest_year_column(df, pattern: str = r"(\d{4})") -> Optional[str]:
    """Return the column name containing the latest year according to pattern."""
    year_cols = {}
    for col in df.columns:
        match = re.search(pattern, str(col))
        if match:
            try:
                year_cols[col] = int(match.group(1))
            except ValueError:
                continue
    if not year_cols:
        return None
    return max(year_cols, key=year_cols.get)
