
import os
import sys
import types
import time
import threading
import logging

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

openai_calls = {}

def _setup_openai(monkeypatch):
    def create(**kwargs):
        openai_calls.update(kwargs)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content='[]'))]
        )
    chat_stub = types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    openai_stub = types.SimpleNamespace(chat=chat_stub)
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

    assert 'images' not in openai_calls
    first_msg = openai_calls['messages'][0]
    assert first_msg['content'][1]['image_url']['url'].startswith('data:image/jpeg;base64,')
    for path in temp_paths:
        assert not os.path.exists(path)


def test_parse_parallel_execution(monkeypatch):
    def fake_convert(_path, **_kwargs):
        return [FakeImage(), FakeImage(), FakeImage()]

    pdf2image_stub = types.SimpleNamespace(convert_from_path=fake_convert)
    monkeypatch.setitem(sys.modules, 'pdf2image', pdf2image_stub)

    lock = threading.Lock()
    running = 0
    concurrency = []

    def create(**_kwargs):
        nonlocal running
        with lock:
            running += 1
            concurrency.append(running)
        time.sleep(0.01)
        with lock:
            running -= 1
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content='[]'))]
        )

    chat_stub = types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    openai_stub = types.SimpleNamespace(chat=chat_stub)
    monkeypatch.setitem(sys.modules, 'openai', openai_stub)
    monkeypatch.setenv('OPENAI_API_KEY', 'x')

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

    mod.parse('dummy.pdf')

    if _pandas_stubbed:
        del sys.modules['pandas']

    assert max(concurrency) > 1


def test_retry_short_prompt(monkeypatch, caplog):
    def fake_convert(_path, **_kwargs):
        return [FakeImage()]

    pdf2image_stub = types.SimpleNamespace(convert_from_path=fake_convert)
    monkeypatch.setitem(sys.modules, "pdf2image", pdf2image_stub)

    calls = []

    def create(**kwargs):
        text = kwargs["messages"][0]["content"][0]["text"]
        calls.append(text)
        if len(calls) == 1:
            content = "invalid"
        else:
            content = "[]"
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=content))]
        )

    chat_stub = types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    openai_stub = types.SimpleNamespace(chat=chat_stub)
    monkeypatch.setitem(sys.modules, "openai", openai_stub)
    monkeypatch.setenv("OPENAI_API_KEY", "x")

    _pandas_stubbed = False
    try:
        import pandas as pd  # noqa: F401
    except ModuleNotFoundError:
        pd = types.ModuleType("pandas")
        sys.modules["pandas"] = pd
        _pandas_stubbed = True
    if not hasattr(pd, "DataFrame"):
        pd.DataFrame = lambda *args, **kwargs: args[0]
        _pandas_stubbed = True

    import importlib
    import smart_price.core.ocr_llm_fallback as mod
    importlib.reload(mod)

    with caplog.at_level(logging.INFO, logger="smart_price"):
        mod.parse("dummy.pdf")

    if _pandas_stubbed:
        del sys.modules["pandas"]

    assert len(calls) == 1


def test_timeout_retry(monkeypatch):
    def fake_convert(_path, **_kwargs):
        return [FakeImage()]

    pdf2image_stub = types.SimpleNamespace(convert_from_path=fake_convert)
    monkeypatch.setitem(sys.modules, "pdf2image", pdf2image_stub)

    calls: list[str] = []

    def create(**_kwargs):
        if not calls:
            calls.append("first")
            raise TimeoutError("boom")
        calls.append("second")
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="[]"))]
        )

    chat_stub = types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    openai_stub = types.SimpleNamespace(chat=chat_stub)
    monkeypatch.setitem(sys.modules, "openai", openai_stub)
    monkeypatch.setenv("OPENAI_API_KEY", "x")

    _pandas_stubbed = False
    try:
        import pandas as pd  # noqa: F401
    except ModuleNotFoundError:
        pd = types.ModuleType("pandas")
        sys.modules["pandas"] = pd
        _pandas_stubbed = True
    if not hasattr(pd, "DataFrame"):
        pd.DataFrame = lambda *args, **kwargs: args[0]
        _pandas_stubbed = True

    import importlib
    import smart_price.core.ocr_llm_fallback as mod
    importlib.reload(mod)

    df = mod.parse("dummy.pdf")
    summary = getattr(df, "page_summary", None)

    if _pandas_stubbed:
        del sys.modules["pandas"]

    assert calls == ["first", "second"]
    assert summary and summary[0]["note"] == "timeout retry"
