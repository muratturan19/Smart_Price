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
@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_agentic_pdf_columns(monkeypatch):
    header = ["Malzeme_Kodu", "Açıklama", "Fiyat"]
    data = ["X1", "Desc", "5"]
    parsed_doc = types.SimpleNamespace(
        chunks=[
            types.SimpleNamespace(
                chunk_type="table_row",
                text="\t".join(header),
                grounding=[types.SimpleNamespace(text=t) for t in header],
            ),
            types.SimpleNamespace(
                chunk_type="table_row",
                text="\t".join(data),
                grounding=[types.SimpleNamespace(text=t) for t in data],
            ),
            types.SimpleNamespace(chunk_type="text", text="foo"),
        ],
        page_summary=[{"page_number": 1, "rows": 1, "status": "success"}],
        token_counts={"input": 1, "output": 1},
    )
    parse_mod = types.ModuleType("agentic_doc.parse")
    parse_mod.parse = lambda *_a, **_kw: [parsed_doc]
    common_mod = types.ModuleType("agentic_doc.common")
    common_mod.RetryableError = Exception
    agentic_pkg = types.ModuleType("agentic_doc")
    agentic_pkg.__path__ = []
    agentic_pkg.parse = parse_mod
    agentic_pkg.common = common_mod
    monkeypatch.setitem(sys.modules, "agentic_doc", agentic_pkg)
    monkeypatch.setitem(sys.modules, "agentic_doc.parse", parse_mod)
    monkeypatch.setitem(sys.modules, "agentic_doc.common", common_mod)

    mod = importlib.import_module("smart_price.core.extract_pdf_agentic")
    importlib.reload(mod)

    pdf_path = os.path.join("tests", "samples", "ESMAKSAN_2025_MART.pdf")
    df = mod.extract_from_pdf_agentic(pdf_path)
    assert set(df.columns) >= {"Malzeme_Kodu", "Açıklama", "Fiyat"}
    assert len(df) == 1
    parsed = df.loc[0, ["Malzeme_Kodu", "Açıklama", "Fiyat"]].to_dict()
    assert parsed == {"Malzeme_Kodu": "X1", "Açıklama": "Desc", "Fiyat": 5.0}
