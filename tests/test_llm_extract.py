import os
import sys
import types
import inspect
from types import FunctionType
import time

# Provide minimal stubs for optional deps before importing project code
_pandas_stubbed = False
try:  # pragma: no cover - pandas may not be installed
    import pandas as pd  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - fallback to stub
    sys.modules['pandas'] = types.ModuleType('pandas')
    _pandas_stubbed = True
if 'pdfplumber' not in sys.modules:
    sys.modules['pdfplumber'] = types.ModuleType('pdfplumber')
if 'tkinter' not in sys.modules:
    tk_stub = types.ModuleType('tkinter')
    tk_stub.filedialog = types.SimpleNamespace()
    tk_stub.simpledialog = types.SimpleNamespace()
    tk_stub.messagebox = types.SimpleNamespace()
    sys.modules['tkinter'] = tk_stub
if 'pdf2image' not in sys.modules:
    sys.modules['pdf2image'] = types.ModuleType('pdf2image')
if 'pytesseract' not in sys.modules:
    sys.modules['pytesseract'] = types.ModuleType('pytesseract')
if 'PIL' not in sys.modules:
    pil_stub = types.ModuleType('PIL')
    image_stub = types.ModuleType('PIL.Image')
    class FakeImg:  # pragma: no cover - simple stub
        pass
    image_stub.Image = FakeImg
    pil_stub.Image = image_stub
    sys.modules['PIL'] = pil_stub
    sys.modules['PIL.Image'] = image_stub
if 'streamlit' not in sys.modules:
    sys.modules['streamlit'] = types.ModuleType('streamlit')
if 'dotenv' not in sys.modules:
    dotenv_stub = types.ModuleType('dotenv')
    dotenv_stub.load_dotenv = lambda: None
    sys.modules['dotenv'] = dotenv_stub

import smart_price.core.extract_pdf as ep  # noqa: E402
from smart_price.core.extract_pdf import extract_from_pdf  # noqa: E402

if _pandas_stubbed:
    del sys.modules['pandas']


def _get_llm_func(log_func):
    """Return the hidden _llm_extract_from_image function."""
    for const in extract_from_pdf.__code__.co_consts:
        if inspect.iscode(const) and const.co_name == '_llm_extract_from_image':
            code_obj = const
            break
    else:  # pragma: no cover - function not found
        raise AssertionError('nested function not found')

    def make_cell(value):
        def inner():
            return value
        return inner.__closure__[0]

    return FunctionType(
        code_obj,
        extract_from_pdf.__globals__,
        '_llm_extract_from_image',
        None,
        (make_cell(log_func),),
    )


class DummyResp:
    def __init__(self, content):
        self.choices = [types.SimpleNamespace(message=types.SimpleNamespace(content=content))]


def _setup_openai(
    monkeypatch,
    content,
    captured_model=None,
    captured_prompt=None,
    captured_client_kwargs=None,
):
    def create(**_kwargs):
        if captured_model is not None:
            captured_model.append(_kwargs.get('model'))
        if captured_prompt is not None:
            msgs = _kwargs.get('messages') or []
            if msgs:
                captured_prompt.append(msgs[0].get('content'))
        return DummyResp(content)

    client_stub = types.SimpleNamespace(
        chat=types.SimpleNamespace(
            completions=types.SimpleNamespace(create=create)
        )
    )

    def openai_constructor(**_kwargs):
        if captured_client_kwargs is not None:
            captured_client_kwargs.append(_kwargs)
        return client_stub

    openai_stub = types.SimpleNamespace(OpenAI=openai_constructor)
    monkeypatch.setitem(sys.modules, 'openai', openai_stub)
    monkeypatch.setenv('OPENAI_API_KEY', 'x')
    monkeypatch.setattr(time, 'sleep', lambda *_: None)
    return openai_stub


def test_llm_extract_valid_json(monkeypatch):
    logs = []
    func = _get_llm_func(logs.append)
    _setup_openai(monkeypatch, '[{"name":"Item","price":"10 TL"}]')
    result = func('ignored')
    assert result == [{
        'Malzeme_Adi': 'Item',
        'Fiyat': 10.0,
        'Para_Birimi': '₺'
    }]
    assert logs[0].startswith("LLM fazı başladı")
    assert logs[-1] == "LLM parsed 1 items"


def test_llm_extract_extra_text(monkeypatch):
    logs = []
    func = _get_llm_func(logs.append)
    content = 'Result is:\n```json\n[{"name":"Foo","price":"5 USD"}]\n```\nthanks'
    _setup_openai(monkeypatch, content)
    result = func('ignored')
    assert result == [{
        'Malzeme_Adi': 'Foo',
        'Fiyat': 5.0,
        'Para_Birimi': '$'
    }]
    assert logs[0].startswith("LLM fazı başladı")
    assert logs[-1] == "LLM parsed 1 items"


def test_llm_extract_invalid_json(monkeypatch):
    logs = []
    func = _get_llm_func(logs.append)
    _setup_openai(monkeypatch, 'not json')
    result = func('ignored')
    assert result == []
    assert any('invalid JSON' in msg for msg in logs)
    assert logs[0].startswith("LLM fazı başladı")
    assert logs[-1] == "LLM returned no data"


def test_llm_custom_model(monkeypatch):
    logs = []
    func = _get_llm_func(logs.append)
    captured = []
    _setup_openai(monkeypatch, '[]', captured)
    monkeypatch.setenv('OPENAI_MODEL', 'foo-model')
    result = func('ignored')
    assert result == []
    assert captured == ['foo-model']


def test_llm_empty_items_logs_excerpt(monkeypatch):
    logs = []
    func = _get_llm_func(logs.append)
    _setup_openai(monkeypatch, '[]')
    text = 'foo\nbar ' * 20
    result = func(text)
    assert result == []
    assert any('no items parsed by' in msg for msg in logs)
    assert 'gpt-4o' in ''.join(logs)


def test_llm_prompt_and_clean(monkeypatch):
    logs = []
    func = _get_llm_func(logs.append)
    captured_prompt = []
    _setup_openai(monkeypatch, '[{"name":"A","price":"4"}]', captured_prompt=captured_prompt)

    cleaned = []

    def fake_clean(text):
        cleaned.append(text)
        return text

    monkeypatch.setattr(ep, 'gpt_clean_text', fake_clean)

    result = func('sample')
    assert cleaned == ['[{"name":"A","price":"4"}]']
    assert captured_prompt[0] == ep.ocr_llm_fallback.DEFAULT_PROMPT
    assert result == [{
        'Malzeme_Adi': 'A',
        'Fiyat': 4.0,
        'Para_Birimi': None
    }]


def test_llm_extract_mismatched_quotes(monkeypatch):
    logs = []
    func = _get_llm_func(logs.append)
    content = "[{name:'Foo', price:'5 USD'}]"
    _setup_openai(monkeypatch, content)
    result = func('ignored')
    assert result == [{
        'Malzeme_Adi': 'Foo',
        'Fiyat': 5.0,
        'Para_Birimi': '$'
    }]


def test_llm_openai_max_retries_env(monkeypatch):
    logs = []
    func = _get_llm_func(logs.append)
    client_args = []
    _setup_openai(monkeypatch, '[]', captured_client_kwargs=client_args)
    monkeypatch.setenv('OPENAI_MAX_RETRIES', '3')
    func('ignored')
    assert client_args[0].get('max_retries') == 3


def test_llm_openai_max_retries_default(monkeypatch):
    logs = []
    func = _get_llm_func(logs.append)
    client_args = []
    _setup_openai(monkeypatch, '[]', captured_client_kwargs=client_args)
    monkeypatch.delenv('OPENAI_MAX_RETRIES', raising=False)
    func('ignored')
    assert client_args[0].get('max_retries') == 0

