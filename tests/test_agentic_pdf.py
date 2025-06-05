import os
import sys
import types
import importlib
import pytest

try:
    import pandas as pd  # noqa: F401

    HAS_PANDAS = True
except ModuleNotFoundError:  # pragma: no cover - optional dep
    HAS_PANDAS = False

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_agentic_pdf_columns(monkeypatch):
    row = {"Malzeme_Kodu": "X1", "Açıklama": "Desc", "Fiyat": "5"}
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

    pdf_path = os.path.join("tests", "samples", "ESMAKSAN_2025_MART.pdf")
    df = mod.extract_from_pdf_agentic(pdf_path)
    assert set(df.columns) >= {"Malzeme_Kodu", "Açıklama", "Fiyat"}
    assert len(df) > 0
