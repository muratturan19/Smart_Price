import sys
import types
import importlib
import pytest

try:
    import pandas as pd  # noqa: F401

    HAS_PANDAS = True
except ModuleNotFoundError:
    HAS_PANDAS = False

if HAS_PANDAS:
    from smart_price.core.extract_pdf_agentic import extract_from_pdf_agentic
else:
    extract_from_pdf_agentic = None


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_agentic_parse_list(monkeypatch):
    row = {"Malzeme_Kodu": "A", "Açıklama": "Item", "Fiyat": 1.0}
    parsed_doc = types.SimpleNamespace(
        chunks=[types.SimpleNamespace(table_row=row)],
        page_summary=[{"page_number": 1, "rows": 1, "status": "success", "note": None}],
        token_counts={"input": 1, "output": 1},
    )

    parse_mod = types.ModuleType("agentic_doc.parse")
    parse_mod.parse = lambda *_a, **_kw: [parsed_doc]
    agentic_pkg = types.ModuleType("agentic_doc")
    agentic_pkg.__path__ = []
    agentic_pkg.parse = parse_mod
    monkeypatch.setitem(sys.modules, "agentic_doc", agentic_pkg)
    monkeypatch.setitem(sys.modules, "agentic_doc.parse", parse_mod)

    mod = importlib.import_module("smart_price.core.extract_pdf_agentic")
    importlib.reload(mod)

    df = mod.extract_from_pdf_agentic("dummy.pdf")
    assert len(df) == 1
    assert df.iloc[0]["Malzeme_Kodu"] == "A"
    assert getattr(df, "page_summary", None) == parsed_doc.page_summary
    assert getattr(df, "token_counts", None) == parsed_doc.token_counts


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_agentic_numeric_headers(monkeypatch):
    row = {0: "A1", 1: "Desc", 2: "5"}
    parsed_doc = types.SimpleNamespace(
        chunks=[types.SimpleNamespace(table_row=row)],
        page_summary=[{"page_number": 1, "rows": 1, "status": "success"}],
        token_counts={"input": 1, "output": 1},
    )

    parse_mod = types.ModuleType("agentic_doc.parse")
    parse_mod.parse = lambda *_a, **_kw: [parsed_doc]
    agentic_pkg = types.ModuleType("agentic_doc")
    agentic_pkg.__path__ = []
    agentic_pkg.parse = parse_mod
    monkeypatch.setitem(sys.modules, "agentic_doc", agentic_pkg)
    monkeypatch.setitem(sys.modules, "agentic_doc.parse", parse_mod)

    mod = importlib.import_module("smart_price.core.extract_pdf_agentic")
    importlib.reload(mod)

    df = mod.extract_from_pdf_agentic("dummy.pdf")
    assert list(df.columns)[:3] == ["Malzeme_Kodu", "Açıklama", "Fiyat"]
    assert df.iloc[0]["Malzeme_Kodu"] == "A1"
    assert df.iloc[0]["Açıklama"] == "Desc"
