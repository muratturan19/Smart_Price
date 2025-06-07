import sys
import types
import importlib
import logging
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
                text="\t".join(header),
                grounding=[types.SimpleNamespace(text=t) for t in header],
            ),
            types.SimpleNamespace(
                chunk_type="table_row",
                text="\t".join(data),
                grounding=[types.SimpleNamespace(text=t) for t in data],
            ),
            types.SimpleNamespace(chunk_type="text", text="not a table"),
        ],
        page_summary=[{"page_number": 1, "rows": 1, "status": "success", "note": None}],
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

    df = mod.extract_from_pdf_agentic("dummy.pdf")
    assert len(df) == 1
    parsed = df.loc[0, ["Malzeme_Kodu", "Açıklama", "Fiyat"]].to_dict()
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
                text="\t".join(header),
                grounding=[types.SimpleNamespace(text=t) for t in header],
            ),
            types.SimpleNamespace(
                chunk_type="table_row",
                text="\t".join(data),
                grounding=[types.SimpleNamespace(text=t) for t in data],
            ),
            types.SimpleNamespace(chunk_type="text", text="ignored text"),
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

    df = mod.extract_from_pdf_agentic("dummy.pdf")
    assert list(df.columns)[:3] == ["Malzeme_Kodu", "Açıklama", "Fiyat"]
    parsed = df.loc[0, ["Malzeme_Kodu", "Açıklama", "Fiyat"]].to_dict()
    assert parsed == {"Malzeme_Kodu": "A1", "Açıklama": "Desc", "Fiyat": 5.0}


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_agentic_prompt_forward(monkeypatch):
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
        ],
        page_summary=None,
        token_counts=None,
    )

    captured = {}

    def fake_parse(path, **kwargs):
        captured.update(kwargs)
        return [parsed_doc]

    parse_mod = types.ModuleType("agentic_doc.parse")
    parse_mod.parse = fake_parse
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

    mod.extract_from_pdf_agentic("dummy.pdf")
    assert captured == {}


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_agentic_default_prompt(monkeypatch):
    header = ["Malzeme_Kodu", "Açıklama", "Fiyat"]
    data = ["X2", "Item", "7"]
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
        ],
        page_summary=None,
        token_counts=None,
    )

    captured = {}

    def fake_parse(path, **kwargs):
        captured.update(kwargs)
        return [parsed_doc]

    parse_mod = types.ModuleType("agentic_doc.parse")
    parse_mod.parse = fake_parse
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

    mod.extract_from_pdf_agentic("dummy.pdf")
    assert captured == {}


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_agentic_debug_output(monkeypatch, tmp_path):
    header = ["Malzeme_Kodu", "Açıklama", "Fiyat"]
    data = ["X", "Desc", "1"]
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
        ],
        page_summary=None,
        token_counts=None,
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

    monkeypatch.setenv("ADE_DEBUG", "1")
    monkeypatch.setenv("SMART_PRICE_DEBUG_DIR", str(tmp_path))

    mod = importlib.import_module("smart_price.core.extract_pdf_agentic")
    importlib.reload(mod)

    df = mod.extract_from_pdf_agentic("dummy.pdf")
    assert not df.empty

    folder = tmp_path / "dummy"
    debug_files = list(folder.glob("ade_chunk_page_*.txt"))
    assert debug_files, "no debug files"
    first_content = debug_files[0].read_text()
    assert "table_row" in first_content


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_grounding_fallback(monkeypatch):
    header = ["Malzeme_Kodu", "Açıklama", "Fiyat"]
    data = ["X3", "Desc", "12"]
    parsed_doc = types.SimpleNamespace(
        chunks=[
            types.SimpleNamespace(
                chunk_type="table_row",
                text="",
                grounding=[types.SimpleNamespace(text=t) for t in header],
            ),
            types.SimpleNamespace(
                chunk_type="table_row",
                text="",
                grounding=[types.SimpleNamespace(text=t) for t in data],
            ),
        ],
        page_summary=None,
        token_counts=None,
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

    df = mod.extract_from_pdf_agentic("dummy.pdf")
    assert len(df) == 1
    parsed = df.loc[0, ["Malzeme_Kodu", "Açıklama", "Fiyat"]].to_dict()
    assert parsed == {"Malzeme_Kodu": "X3", "Açıklama": "Desc", "Fiyat": 12.0}


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_agentic_no_rows_logged(monkeypatch, caplog):
    header = ["Malzeme_Kodu", "Açıklama", "Fiyat"]
    data = ["A", "Item", "1"]
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
        ],
        page_summary=[{"page_number": 1, "rows": 1, "status": "success"}],
        token_counts=None,
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

    monkeypatch.setattr(mod, "_map_columns", lambda df: df.iloc[:0])

    with caplog.at_level(logging.INFO, logger="smart_price"):
        with pytest.raises(ValueError):
            mod.extract_from_pdf_agentic("dummy.pdf")

    messages = "\n".join(r.getMessage() for r in caplog.records)
    assert "no rows extracted" in messages
    assert "preview=" in messages
    assert "page_summary" in messages
