import sys
import types
import importlib
from pathlib import Path

# Provide a stub for python-dotenv if not installed
dotenv_stub = sys.modules.get('dotenv', types.ModuleType('dotenv'))
if not hasattr(dotenv_stub, 'load_dotenv'):
    dotenv_stub.load_dotenv = lambda *_args, **_kw: None
if not hasattr(dotenv_stub, 'find_dotenv'):
    dotenv_stub.find_dotenv = lambda *_args, **_kw: ''
sys.modules['dotenv'] = dotenv_stub

import smart_price.config as cfg


def test_defaults(monkeypatch):
    dotenv_stub = types.ModuleType('dotenv')
    dotenv_stub.load_dotenv = lambda *_a, **_k: None
    dotenv_stub.find_dotenv = lambda *_a, **_k: ''
    monkeypatch.setitem(sys.modules, 'dotenv', dotenv_stub)
    for name in ("MASTER_DB_PATH", "IMAGE_DIR", "SALES_APP_DIR", "PRICE_APP_DIR", "DEBUG_DIR"):
        monkeypatch.delenv(name, raising=False)
    importlib.reload(cfg)
    root = Path(__file__).resolve().parent.parent
    assert cfg.MASTER_DB_PATH == root / "master.db"
    assert cfg.IMAGE_DIR == root / "images"
    assert cfg.SALES_APP_DIR == root / "sales_app"
    assert cfg.PRICE_APP_DIR == root / "smart_price"
    assert cfg.DEBUG_DIR == root / "LLM_Output_db"


def test_env_and_config_overrides(tmp_path, monkeypatch):
    dotenv_stub = types.ModuleType('dotenv')
    dotenv_stub.load_dotenv = lambda *_a, **_k: None
    dotenv_stub.find_dotenv = lambda *_a, **_k: ''
    monkeypatch.setitem(sys.modules, 'dotenv', dotenv_stub)
    config_path = tmp_path / "config.json"
    config_path.write_text('{"IMAGE_DIR": "imx"}')
    monkeypatch.setattr(cfg, "_REPO_ROOT", tmp_path)
    monkeypatch.setenv("MASTER_DB_PATH", str(tmp_path / "db.sqlite"))
    monkeypatch.setenv("DEBUG_DIR", str(tmp_path / "dbg"))
    monkeypatch.setenv("IMAGE_DIR", str(tmp_path / "img_env"))
    monkeypatch.setenv("SALES_APP_DIR", str(tmp_path / "sales"))
    monkeypatch.setenv("PRICE_APP_DIR", str(tmp_path / "price"))
    importlib.reload(cfg)
    cfg.load_config()
    assert cfg.MASTER_DB_PATH == tmp_path / "db.sqlite"
    assert cfg.IMAGE_DIR == tmp_path / "img_env"
    assert cfg.SALES_APP_DIR == tmp_path / "sales"
    assert cfg.PRICE_APP_DIR == tmp_path / "price"
    assert cfg.DEBUG_DIR == tmp_path / "dbg"
