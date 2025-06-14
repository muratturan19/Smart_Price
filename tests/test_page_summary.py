import sys
import types
import pytest

# Provide minimal stubs for optional deps before importing project code
if 'PIL' not in sys.modules:
    pil_stub = types.ModuleType('PIL')
    image_stub = types.ModuleType('PIL.Image')
    class FakeImg:
        pass
    image_stub.Image = FakeImg
    pil_stub.Image = image_stub
    sys.modules['PIL'] = pil_stub
    sys.modules['PIL.Image'] = image_stub

dotenv_stub = types.ModuleType('dotenv')
dotenv_stub.load_dotenv = lambda *_args, **_kw: None
sys.modules['dotenv'] = dotenv_stub

# Ensure repo root is on path

try:
    import pandas as pd  # noqa: F401
    HAS_PANDAS = True
except ModuleNotFoundError:
    HAS_PANDAS = False

if HAS_PANDAS:
    from smart_price.core.extract_pdf import extract_from_pdf
    import smart_price.core.extract_pdf as pdf_mod
else:
    extract_from_pdf = None

@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_extract_from_pdf_summary(monkeypatch):
    def fake_parse(_path, *_, **__):
        import pandas as pd
        df = pd.DataFrame({
            "Malzeme_Kodu": ["A"],
            "Açıklama": ["Item"],
            "Fiyat": [1.0],
            "Sayfa": [1],
        })
        object.__setattr__(df, "page_summary", [
            {"page_number": 1, "rows": 1, "status": "success", "note": None},
            {"page_number": 2, "rows": 0, "status": "empty", "note": None},
        ])
        return df

    monkeypatch.setattr(pdf_mod.ocr_llm_fallback, "parse", fake_parse)

    df = extract_from_pdf("dummy.pdf")
    summary = getattr(df, "page_summary", None)
    assert summary and len(summary) == 2
    assert summary[0]["page_number"] == 1
    assert summary[0]["rows"] == 1
    assert summary[0]["status"] == "success"
    assert summary[1]["page_number"] == 2
    assert summary[1]["rows"] == 0
    assert summary[1]["status"] == "empty"

@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_ocr_llm_fallback_summary(monkeypatch):
    class FakeImage:
        def __init__(self, data=b"img"):
            self.data = data
        def save(self, path, format=None):
            with open(path, "wb") as f:
                f.write(self.data)
    def fake_convert(_path, **_kw):
        return [FakeImage(), FakeImage()]
    monkeypatch.setitem(sys.modules, "pdf2image", types.SimpleNamespace(convert_from_path=fake_convert))

    contents = [
        '[{"Malzeme_Kodu":"A","Açıklama":"X","Fiyat":"1"}]',
        '[]'
    ]
    async def create(**kwargs):
        content = contents.pop(0)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=content))])
    openai_stub = types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))
    openai_stub.AsyncOpenAI = lambda *a, **kw: openai_stub
    openai_stub.OpenAI = openai_stub.AsyncOpenAI
    monkeypatch.setitem(sys.modules, 'openai', openai_stub)
    monkeypatch.setenv('OPENAI_API_KEY', 'x')
    monkeypatch.setenv('RETRY_DELAY_BASE', '0')

    import importlib
    import smart_price.core.ocr_llm_fallback as mod
    importlib.reload(mod)

    df = mod.parse('dummy.pdf')
    summary = getattr(df, 'page_summary', None)
    assert summary and len(summary) == 2
    assert summary[0]['rows'] == 1
    assert summary[0]['status'] == 'success'
    assert summary[1]['rows'] == 0
    assert summary[1]['status'] == 'empty'
