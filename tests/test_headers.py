import sys
import types
import importlib
import logging

def _import_module(monkeypatch):
    """Import extract_excel with minimal stubs if pandas is missing."""
    try:
        import pandas  # noqa: F401
    except ModuleNotFoundError:
        stub = types.ModuleType("pandas")
        stub.DataFrame = type("DataFrame", (), {})
        monkeypatch.setitem(sys.modules, "pandas", stub)
    for name in ("pdfplumber", "tkinter", "pdf2image", "pytesseract", "streamlit"):
        if name not in sys.modules:
            monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    module = importlib.import_module("smart_price.core.extract_excel")
    importlib.reload(module)
    return module


def test_item_headers_only_in_code(monkeypatch):
    ee = _import_module(monkeypatch)
    headers = {"item name", "item no", "item number", "item #"}
    assert headers.issubset(ee.POSSIBLE_CODE_HEADERS)
    normalized = {ee._norm_header(h) for h in headers}
    code_normalized = {ee._norm_header(h) for h in ee.POSSIBLE_CODE_HEADERS}
    for h in normalized:
        assert h in code_normalized
        assert h not in ee.POSSIBLE_DESC_HEADERS


def test_malzeme_header_detected(monkeypatch):
    ee = _import_module(monkeypatch)
    df = types.SimpleNamespace(columns=["MALZEME", "Fiyat"])
    code_col, short_col, desc_col, price_col, currency_col = ee.find_columns_in_excel(df)
    assert code_col == "MALZEME"


def test_column_mapping_logged(monkeypatch, caplog):
    ee = _import_module(monkeypatch)
    df = types.SimpleNamespace(columns=["MALZEME", "Fiyat", "Other"])
    with caplog.at_level(logging.INFO, logger="smart_price"):
        ee.find_columns_in_excel(df)
    messages = "\n".join(r.getMessage() for r in caplog.records)
    assert "excel column mapping" in messages
    assert "MALZEME" in messages
    assert "Other" in messages
