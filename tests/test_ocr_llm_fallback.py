
import os
import sys
import types

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

# Ensure repo root is on path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

openai_calls = {}

def _setup_openai(monkeypatch):
    def create(**kwargs):
        openai_calls.update(kwargs)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content='[]'))]
        )
    client_stub = types.SimpleNamespace(
        chat=types.SimpleNamespace(
            completions=types.SimpleNamespace(create=create)
        )
    )
    openai_stub = types.SimpleNamespace(OpenAI=lambda **_kw: client_stub)
    monkeypatch.setitem(sys.modules, 'openai', openai_stub)
    monkeypatch.setenv('OPENAI_API_KEY', 'x')

class FakeImage:
    def __init__(self, data=b'img'):
        self.data = data
    def save(self, path, format=None):
        with open(path, 'wb') as f:
            f.write(self.data)

def test_parse_sends_bytes_and_cleans_tmp(monkeypatch):
    # Stub pdf2image
    def fake_convert(_path, **_kwargs):
        return [FakeImage()]
    pdf2image_stub = types.SimpleNamespace(convert_from_path=fake_convert)
    monkeypatch.setitem(sys.modules, 'pdf2image', pdf2image_stub)

    _setup_openai(monkeypatch)
    _pandas_stubbed = False
    try:
        import pandas as pd  # noqa: F401
    except ModuleNotFoundError:
        pd = types.ModuleType('pandas')
        sys.modules['pandas'] = pd
        _pandas_stubbed = True
    if not hasattr(pd, 'DataFrame'):
        pd.DataFrame = lambda *args, **kwargs: args[0]
        _pandas_stubbed = True

    import importlib
    import smart_price.core.ocr_llm_fallback as mod
    importlib.reload(mod)
    assert hasattr(mod.pd, "DataFrame")

    temp_paths = []
    orig_named = mod.tempfile.NamedTemporaryFile

    def fake_ntf(*args, **kwargs):
        tmp = orig_named(*args, **kwargs)
        temp_paths.append(tmp.name)
        return tmp

    monkeypatch.setattr(mod.tempfile, 'NamedTemporaryFile', fake_ntf)
    mod.parse('dummy.pdf')

    if _pandas_stubbed:
        del sys.modules['pandas']

    assert openai_calls.get('images')[0]['image'] == b'img'
    assert not any('image_url' in c for msg in openai_calls['messages'] for c in msg['content'])
    for path in temp_paths:
        assert not os.path.exists(path)
