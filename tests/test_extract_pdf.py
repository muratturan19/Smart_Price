import importlib
import logging
import sys
import types
import os

from tests.helpers import extract_pdf

import smart_price.config as cfg


def test_esmaksn_pdf_threshold():
    df = extract_pdf.parse("tests/samples/ESMAKSAN_2025_MART.pdf")
    assert len(df) >= 1600
    assert df['Malzeme_Kodu'].notna().mean() >= 0.7


def test_poppler_missing_warning(monkeypatch, tmp_path, caplog):
    orig_env = os.environ.get('POPPLER_PATH')
    dotenv_stub = types.ModuleType('dotenv')
    dotenv_stub.load_dotenv = lambda *_a, **_k: None
    dotenv_stub.find_dotenv = lambda *_a, **_k: ''
    monkeypatch.setitem(sys.modules, 'dotenv', dotenv_stub)
    monkeypatch.setenv('POPPLER_PATH', str(tmp_path / 'bin'))

    with caplog.at_level(logging.ERROR, logger='smart_price'):
        importlib.reload(cfg)

    messages = "\n".join(r.getMessage() for r in caplog.records)
    assert 'poppler' in messages.lower()
    assert 'readme' in messages.lower()

    if orig_env is None:
        monkeypatch.delenv('POPPLER_PATH', raising=False)
    else:
        monkeypatch.setenv('POPPLER_PATH', orig_env)
    importlib.reload(cfg)
