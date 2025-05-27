import os
import sys
import types
import inspect
import pytest
import time

# Ensure repo root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Provide minimal stubs for optional deps
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
if 'streamlit' not in sys.modules:
    sys.modules['streamlit'] = types.ModuleType('streamlit')
if 'dotenv' not in sys.modules:
    dotenv_stub = types.ModuleType('dotenv')
    dotenv_stub.load_dotenv = lambda: None
    sys.modules['dotenv'] = dotenv_stub

from core.extract_pdf import extract_from_pdf

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

    from types import FunctionType
    return FunctionType(code_obj, extract_from_pdf.__globals__,
                        '_llm_extract_from_image', None, (make_cell(log_func),))


class DummyResp:
    def __init__(self, content):
        self.choices = [types.SimpleNamespace(message=types.SimpleNamespace(content=content))]


def _setup_openai(monkeypatch, content):
    class Chat:
        @staticmethod
        def create(**kwargs):
            return DummyResp(content)

    openai_stub = types.SimpleNamespace(ChatCompletion=Chat, api_key=None)
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
        'Para_Birimi': 'TRY'
    }]
    assert logs == []


def test_llm_extract_extra_text(monkeypatch):
    logs = []
    func = _get_llm_func(logs.append)
    content = 'Result is:\n```json\n[{"name":"Foo","price":"5 USD"}]\n```\nthanks'
    _setup_openai(monkeypatch, content)
    result = func('ignored')
    assert result == [{
        'Malzeme_Adi': 'Foo',
        'Fiyat': 5.0,
        'Para_Birimi': 'USD'
    }]
    assert logs == []


def test_llm_extract_invalid_json(monkeypatch):
    logs = []
    func = _get_llm_func(logs.append)
    _setup_openai(monkeypatch, 'not json')
    result = func('ignored')
    assert result == []
    assert any('invalid JSON' in msg for msg in logs)

