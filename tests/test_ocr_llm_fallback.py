
import os
import sys
import types
import time
import threading
import logging

from smart_price.core.extract_pdf import PAGE_IMAGE_EXT

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
    openai_calls.clear()
    def create(**kwargs):
        openai_calls.update(kwargs)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content='[]'))]
        )
    chat_stub = types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    openai_stub = types.SimpleNamespace(
        chat=chat_stub,
        api_requestor=types.SimpleNamespace(_DEFAULT_NUM_RETRIES=None),
    )
    openai_stub.AsyncOpenAI = lambda *a, **kw: openai_stub
    openai_stub.OpenAI = openai_stub.AsyncOpenAI
    monkeypatch.setitem(sys.modules, 'openai', openai_stub)
    monkeypatch.setenv('OPENAI_API_KEY', 'x')
    monkeypatch.setenv('MAX_RETRY_WAIT_TIME', '0')
    monkeypatch.setenv('RETRY_DELAY_BASE', '0')

class FakeImage:
    def __init__(self, data=b'img'):
        self.data = data
    def save(self, path, format=None):
        if hasattr(path, 'write'):
            path.write(self.data)
        else:
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
        class FakeDF(list):
            pass
        pd.DataFrame = FakeDF
        _pandas_stubbed = True

    import importlib
    import smart_price.config as conf
    import smart_price.core.ocr_llm_fallback as mod
    importlib.reload(conf)
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
    mime = "jpeg" if PAGE_IMAGE_EXT in {".jpg", ".jpeg"} else PAGE_IMAGE_EXT.lstrip(".")
    assert first_msg['content'][1]['image_url']['url'].startswith(f'data:image/{mime};base64,')
    for path in temp_paths:
        assert not os.path.exists(path)


def test_openai_max_retries_env(monkeypatch):
    def fake_convert(_path, **_kwargs):
        return [FakeImage()]

    pdf2image_stub = types.SimpleNamespace(convert_from_path=fake_convert)
    monkeypatch.setitem(sys.modules, "pdf2image", pdf2image_stub)

    _setup_openai(monkeypatch)
    monkeypatch.setenv("OPENAI_MAX_RETRIES", "5")

    import importlib
    import smart_price.config as conf
    import smart_price.core.ocr_llm_fallback as mod
    importlib.reload(conf)
    importlib.reload(mod)

    mod.parse("dummy.pdf")

    openai_mod = sys.modules["openai"]
    assert openai_mod.api_requestor._DEFAULT_NUM_RETRIES == 5


def test_openai_max_retries_default(monkeypatch):
    def fake_convert(_path, **_kwargs):
        return [FakeImage()]

    pdf2image_stub = types.SimpleNamespace(convert_from_path=fake_convert)
    monkeypatch.setitem(sys.modules, "pdf2image", pdf2image_stub)

    _setup_openai(monkeypatch)
    monkeypatch.delenv("OPENAI_MAX_RETRIES", raising=False)

    import importlib
    import smart_price.config as conf
    import smart_price.core.ocr_llm_fallback as mod
    importlib.reload(conf)
    importlib.reload(mod)

    mod.parse("dummy.pdf")

    openai_mod = sys.modules["openai"]
    assert openai_mod.api_requestor._DEFAULT_NUM_RETRIES == 0


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
    openai_stub.AsyncOpenAI = lambda *a, **kw: openai_stub
    openai_stub.OpenAI = openai_stub.AsyncOpenAI
    openai_stub.OpenAI = openai_stub.AsyncOpenAI
    openai_stub.OpenAI = openai_stub.AsyncOpenAI
    openai_stub.OpenAI = openai_stub.AsyncOpenAI
    openai_stub.OpenAI = openai_stub.AsyncOpenAI
    monkeypatch.setitem(sys.modules, 'openai', openai_stub)
    monkeypatch.setenv('OPENAI_API_KEY', 'x')
    monkeypatch.setenv('RETRY_DELAY_BASE', '0')

    _pandas_stubbed = False
    try:
        import pandas as pd  # noqa: F401
    except ModuleNotFoundError:
        pd = types.ModuleType('pandas')
        sys.modules['pandas'] = pd
        class FakeDF(list):
            pass
        pd.DataFrame = FakeDF
        _pandas_stubbed = True

    import importlib
    import smart_price.config as conf
    import smart_price.core.ocr_llm_fallback as mod
    importlib.reload(conf)
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
    openai_stub.AsyncOpenAI = lambda *a, **kw: openai_stub
    monkeypatch.setitem(sys.modules, "openai", openai_stub)
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv('RETRY_DELAY_BASE', '0')

    _pandas_stubbed = False
    try:
        import pandas as pd  # noqa: F401
    except ModuleNotFoundError:
        pd = types.ModuleType("pandas")
        sys.modules["pandas"] = pd
        class FakeDF(list):
            pass
        pd.DataFrame = FakeDF
        _pandas_stubbed = True

    import importlib
    import smart_price.config as conf
    import smart_price.core.ocr_llm_fallback as mod
    importlib.reload(conf)
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
    openai_stub.AsyncOpenAI = lambda *a, **kw: openai_stub
    monkeypatch.setitem(sys.modules, "openai", openai_stub)
    monkeypatch.setenv("OPENAI_API_KEY", "x")

    _pandas_stubbed = False
    try:
        import pandas as pd  # noqa: F401
    except ModuleNotFoundError:
        pd = types.ModuleType("pandas")
        sys.modules["pandas"] = pd
        class FakeDF(list):
            pass
        pd.DataFrame = FakeDF
        _pandas_stubbed = True

    import importlib
    import smart_price.config as conf
    import smart_price.core.ocr_llm_fallback as mod
    importlib.reload(conf)
    importlib.reload(mod)

    df = mod.parse("dummy.pdf")
    summary = getattr(df, "page_summary", None)

    if _pandas_stubbed:
        del sys.modules["pandas"]

    assert calls == ["first", "second"]
    assert summary and summary[0]["note"] == "timeout retry"


def test_api_timeout_retry(monkeypatch):
    def fake_convert(_path, **_kwargs):
        return [FakeImage()]

    pdf2image_stub = types.SimpleNamespace(convert_from_path=fake_convert)
    monkeypatch.setitem(sys.modules, "pdf2image", pdf2image_stub)

    class FakeAPITimeoutError(Exception):
        pass

    calls: list[str] = []

    def create(**_kwargs):
        if not calls:
            calls.append("first")
            raise FakeAPITimeoutError("boom")
        calls.append("second")
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="[]"))]
        )

    chat_stub = types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    openai_stub = types.SimpleNamespace(
        chat=chat_stub,
        APITimeoutError=FakeAPITimeoutError,
        error=types.SimpleNamespace(Timeout=FakeAPITimeoutError),
    )
    openai_stub.AsyncOpenAI = lambda *a, **kw: openai_stub
    openai_stub.OpenAI = openai_stub.AsyncOpenAI
    monkeypatch.setitem(sys.modules, "openai", openai_stub)
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv('RETRY_DELAY_BASE', '0')

    _pandas_stubbed = False
    try:
        import pandas as pd  # noqa: F401
    except ModuleNotFoundError:
        pd = types.ModuleType("pandas")
        sys.modules["pandas"] = pd
        class FakeDF(list):
            pass
        pd.DataFrame = FakeDF
        _pandas_stubbed = True

    import importlib
    import smart_price.config as conf
    import smart_price.core.ocr_llm_fallback as mod
    importlib.reload(conf)
    importlib.reload(mod)

    df = mod.parse("dummy.pdf")
    summary = getattr(df, "page_summary", None)

    if _pandas_stubbed:
        del sys.modules["pandas"]

    assert calls == ["first", "second"]
    assert summary and summary[0]["note"] == "timeout retry"


def test_connection_error_retry(monkeypatch):
    def fake_convert(_path, **_kwargs):
        return [FakeImage()]

    pdf2image_stub = types.SimpleNamespace(convert_from_path=fake_convert)
    monkeypatch.setitem(sys.modules, "pdf2image", pdf2image_stub)

    class FakeConnError(Exception):
        pass

    calls: list[str] = []

    def create(**_kwargs):
        if not calls:
            calls.append("first")
            raise FakeConnError("boom")
        calls.append("second")
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="[]"))]
        )

    chat_stub = types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    openai_stub = types.SimpleNamespace(
        chat=chat_stub,
        APIConnectionError=FakeConnError,
        error=types.SimpleNamespace(APIConnectionError=FakeConnError),
    )
    openai_stub.AsyncOpenAI = lambda *a, **kw: openai_stub
    openai_stub.OpenAI = openai_stub.AsyncOpenAI
    monkeypatch.setitem(sys.modules, "openai", openai_stub)
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv('RETRY_DELAY_BASE', '0')

    _pandas_stubbed = False
    try:
        import pandas as pd  # noqa: F401
    except ModuleNotFoundError:
        pd = types.ModuleType("pandas")
        sys.modules["pandas"] = pd

        class FakeDF(list):
            pass

        pd.DataFrame = FakeDF
        _pandas_stubbed = True

    import importlib
    import smart_price.config as conf
    import smart_price.core.ocr_llm_fallback as mod
    importlib.reload(conf)
    importlib.reload(mod)

    df = mod.parse("dummy.pdf")
    summary = getattr(df, "page_summary", None)

    if _pandas_stubbed:
        del sys.modules["pandas"]

    assert calls == ["first", "second"]
    assert summary and summary[0]["note"] == "timeout retry"


def test_retry_limit(monkeypatch):
    def fake_convert(_path, **_kwargs):
        return [FakeImage()]

    pdf2image_stub = types.SimpleNamespace(convert_from_path=fake_convert)
    monkeypatch.setitem(sys.modules, "pdf2image", pdf2image_stub)

    calls: list[str] = []

    def create(**_kwargs):
        calls.append("call")
        raise TimeoutError("boom")

    chat_stub = types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    openai_stub = types.SimpleNamespace(chat=chat_stub)
    openai_stub.AsyncOpenAI = lambda *a, **kw: openai_stub
    monkeypatch.setitem(sys.modules, "openai", openai_stub)
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("MAX_RETRIES", "1")
    monkeypatch.setenv("MAX_RETRY_WAIT_TIME", "0")
    monkeypatch.setenv('RETRY_DELAY_BASE', '0')

    _pandas_stubbed = False
    try:
        import pandas as pd  # noqa: F401
    except ModuleNotFoundError:
        pd = types.ModuleType("pandas")
        sys.modules["pandas"] = pd
        class FakeDF(list):
            pass
        pd.DataFrame = FakeDF
        _pandas_stubbed = True

    import importlib
    import smart_price.config as conf
    import smart_price.core.ocr_llm_fallback as mod
    importlib.reload(conf)
    importlib.reload(mod)

    df = mod.parse("dummy.pdf")
    summary = getattr(df, "page_summary", None)

    if _pandas_stubbed:
        del sys.modules["pandas"]

    assert calls == ["call", "call"]
    assert summary and summary[0]["status"] == "error"
    assert summary and summary[0]["note"] == "gave up"


def test_timeout_split(monkeypatch):
    cropping: list[tuple[int, int, int, int]] = []

    class FakeImage:
        def __init__(self, w: int = 10, h: int = 10):
            self.size = (w, h)

        def crop(self, box):
            cropping.append(box)
            w = box[2] - box[0]
            h = box[3] - box[1]
            return FakeImage(w, h)

        def save(self, path, format=None):
            if hasattr(path, "write"):
                path.write(b"img")
            else:
                with open(path, "wb") as f:
                    f.write(b"img")

    def fake_convert(_path, **_kwargs):
        return [FakeImage()]

    pdf2image_stub = types.SimpleNamespace(convert_from_path=fake_convert)
    monkeypatch.setitem(sys.modules, "pdf2image", pdf2image_stub)

    calls: list[str] = []

    def create(**_kwargs):
        calls.append("call")
        if len(calls) == 1:
            raise TimeoutError("boom")
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="[]"))]
        )

    chat_stub = types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    openai_stub = types.SimpleNamespace(chat=chat_stub)
    openai_stub.AsyncOpenAI = lambda *a, **kw: openai_stub
    monkeypatch.setitem(sys.modules, "openai", openai_stub)
    monkeypatch.setenv("OPENAI_API_KEY", "x")

    _pandas_stubbed = False
    try:
        import pandas as pd  # noqa: F401
    except ModuleNotFoundError:
        pd = types.ModuleType("pandas")
        sys.modules["pandas"] = pd

        class FakeDF(list):
            pass

        pd.DataFrame = FakeDF
        _pandas_stubbed = True

    import importlib
    import smart_price.config as conf
    import smart_price.core.ocr_llm_fallback as mod
    importlib.reload(conf)
    importlib.reload(mod)

    df = mod.parse("dummy.pdf")
    summary = getattr(df, "page_summary", None)

    if _pandas_stubbed:
        del sys.modules["pandas"]

    assert cropping == [(0, 0, 10, 5), (0, 5, 10, 10)]
    assert len(calls) == 3
    assert summary and len(summary) == 2
    assert summary[0]["note"] == "timeout split"
    assert summary[1]["note"] == "timeout split"


def test_openai_request_timeout(monkeypatch):
    def fake_convert(_path, **_kwargs):
        return [FakeImage()]

    pdf2image_stub = types.SimpleNamespace(convert_from_path=fake_convert)
    monkeypatch.setitem(sys.modules, "pdf2image", pdf2image_stub)

    _setup_openai(monkeypatch)
    monkeypatch.setenv("OPENAI_REQUEST_TIMEOUT", "42")
    openai_mod = sys.modules["openai"]
    captured = {}

    def _ctor(*_a, **kw):
        captured.update(kw)
        return openai_mod

    monkeypatch.setattr(openai_mod, "OpenAI", _ctor)

    import importlib
    import smart_price.config as conf
    import smart_price.core.ocr_llm_fallback as mod
    importlib.reload(conf)
    importlib.reload(mod)

    mod.parse("dummy.pdf")

    assert captured.get("timeout") == 42.0


def test_llm_workers_env(monkeypatch):
    def fake_convert(_path, **_kwargs):
        return [FakeImage(), FakeImage(), FakeImage()]

    pdf2image_stub = types.SimpleNamespace(convert_from_path=fake_convert)
    monkeypatch.setitem(sys.modules, "pdf2image", pdf2image_stub)

    _setup_openai(monkeypatch)
    monkeypatch.setenv("SMART_PRICE_LLM_WORKERS", "1")

    import importlib
    import smart_price.config as conf
    import smart_price.core.ocr_llm_fallback as mod
    importlib.reload(conf)
    importlib.reload(mod)

    captured = {}
    from concurrent.futures import ThreadPoolExecutor as RealExecutor

    class CaptureExecutor(RealExecutor):
        def __init__(self, *a, **kw):
            captured["max_workers"] = kw.get("max_workers") if "max_workers" in kw else (a[0] if a else None)
            super().__init__(*a, **kw)

    monkeypatch.setattr(mod, "ThreadPoolExecutor", CaptureExecutor)

    mod.parse("dummy.pdf")

    assert captured.get("max_workers") == 1
