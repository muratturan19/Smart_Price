import os
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
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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
    class FakePage:
        def __init__(self, num, text=""):
            self.page_number = num
            self._text = text
        def extract_text(self):
            return self._text
        def extract_tables(self):
            return []
    class FakePDF:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            pass
        @property
        def pages(self):
            return [FakePage(1, "ItemA    10"), FakePage(2, "")]
    monkeypatch.setattr(sys.modules.get("pdfplumber"), "open", lambda *_a, **_k: FakePDF(), raising=False)
    monkeypatch.setattr(pdf_mod, "MIN_ROWS_PARSER", 0)
    monkeypatch.setattr(pdf_mod, "MIN_CODE_RATIO", 0)

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
    def create(**kwargs):
        content = contents.pop(0)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=content))])
    openai_stub = types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))
    monkeypatch.setitem(sys.modules, 'openai', openai_stub)
    monkeypatch.setenv('OPENAI_API_KEY', 'x')

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
