import os
import re
from typing import Optional


def normalize_price(price_str: Optional[str], *, style: str = "eu") -> Optional[float]:
    """Convert a raw price string to a float value.

    Parameters
    ----------
    price_str : str or Any
        String representation of the price. Currency symbols and thousand
        separators are allowed.

    style : {'eu', 'en'}, optional
        ``'eu'`` parses European style numbers like ``1.234,56`` while ``'en'``
        handles English style ``1,234.56``. Defaults to ``'eu'``.

    Returns
    -------
    float or None
        Parsed price as a ``float`` if successful, otherwise ``None``.
    """
    if price_str is None:
        return None
    if style not in {"eu", "en"}:
        raise ValueError("style must be 'eu' or 'en'")

    price_str = str(price_str).strip()
    price_str = re.sub(r"[^\d,\.]+", "", price_str)

    if style == "eu":
        if "," in price_str and "." in price_str:
            if price_str.rfind(".") < price_str.rfind(","):
                price_str = price_str.replace(".", "").replace(",", ".")
        elif "," in price_str:
            price_str = price_str.replace(",", ".")
    else:  # English style
        if "," in price_str and "." in price_str:
            if price_str.rfind(",") < price_str.rfind("."):
                price_str = price_str.replace(",", "")
            else:
                price_str = price_str.replace(".", "").replace(",", ".")
        elif "," in price_str:
            price_str = price_str.replace(",", "")

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


def detect_brand(text: str) -> Optional[str]:
    """Try to infer brand name from a file name.

    The function is intentionally simple. If ``text`` looks like a file
    path, the first textual token in the base name (without extension) is
    returned. Otherwise ``None`` is yielded.

    Parameters
    ----------
    text : str
        File path or name that potentially encodes the brand name.

    Returns
    -------
    str or None
        Detected brand name if any, otherwise ``None``.
    """
    if not text:
        return None

    base = os.path.basename(str(text))
    match = re.search(r"\.([A-Za-z0-9]{2,4})$", base)
    if match:
        base = os.path.splitext(base)[0]
        tokens = re.split(r"[\s_-]+", base)
        brand_parts = []
        for token in tokens:
            if not token:
                continue
            if not brand_parts:
                if re.search(r"[A-Za-z]", token):
                    brand_parts.append(token)
                continue
            if re.match(r"[A-Z].*", token) or token.isupper():
                brand_parts.append(token)
            else:
                break
        if brand_parts:
            return " ".join(brand_parts)
    return None


CODE_DESC_PATTERNS = [
    re.compile(r"^\((?P<code>[A-Z0-9\-/]{3,})\)\s*(?P<desc>.+)$"),
    re.compile(r"^(?P<desc>.+?)\s*\((?P<code>[A-Z0-9\-/]{3,})\)$"),
    re.compile(r"^(?P<code>[A-Z0-9\-/]{3,})\s*/\s*(?P<desc>.+)$"),
    re.compile(r"^(?P<desc>.+?)\s*/\s*(?P<code>[A-Z0-9\-/]{3,})$"),
]

def split_code_description(text: str) -> tuple[Optional[str], str]:
    """Split a product text into code and description parts.

    The helper tries multiple patterns to recognise formats such as
    ``CODE / Description`` or ``Description (CODE)`` before falling
    back to a simple prefix-based extraction.

    Parameters
    ----------
    text : str
        Raw product text possibly containing a product code.

    Returns
    -------
    tuple
        ``(code, description)`` where ``code`` may be ``None`` if no code
        could be detected.
    """
    if not text:
        return None, ""
    text = str(text).strip()
    for pat in CODE_DESC_PATTERNS:
        m = pat.match(text)
        if m:
            return m.group("code").strip(), m.group("desc").strip()
    m = re.match(r"^([A-Z0-9\-/]{3,})\s+(.*)$", text)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None, text

