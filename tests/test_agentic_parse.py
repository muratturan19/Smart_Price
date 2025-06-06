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
    header = ["Malzeme_Kodu", "Açıklama", "Fiyat"]
    data = ["A", "Item", "1"]
    parsed_doc = types.SimpleNamespace(
        chunks=[
            types.SimpleNamespace(
                chunk_type="table_row",
                grounding=[types.SimpleNamespace(text=t) for t in header],
            ),
            types.SimpleNamespace(
                chunk_type="table_row",
                grounding=[types.SimpleNamespace(text=t) for t in data],
            ),
        ],
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
    parsed = df.to_dict("records")[0]
    assert parsed == {"Malzeme_Kodu": "A", "Açıklama": "Item", "Fiyat": 1.0}
    assert getattr(df, "page_summary", None) == parsed_doc.page_summary
    assert getattr(df, "token_counts", None) == parsed_doc.token_counts


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_agentic_numeric_headers(monkeypatch):
    header = ["Malzeme Kodu", "Açıklama", "Fiyat"]
    data = ["A1", "Desc", "5"]
    parsed_doc = types.SimpleNamespace(
        chunks=[
            types.SimpleNamespace(
                chunk_type="table_row",
                grounding=[types.SimpleNamespace(text=t) for t in header],
            ),
            types.SimpleNamespace(
                chunk_type="table_row",
                grounding=[types.SimpleNamespace(text=t) for t in data],
            ),
        ],
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
    parsed = df.loc[0, ["Malzeme_Kodu", "Açıklama", "Fiyat"]].to_dict()
    assert parsed == {"Malzeme_Kodu": "A1", "Açıklama": "Desc", "Fiyat": 5.0}
