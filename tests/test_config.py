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

import smart_price.config as cfg  # noqa: E402


def test_defaults(monkeypatch):
    dotenv_stub = types.ModuleType('dotenv')
    dotenv_stub.load_dotenv = lambda *_a, **_k: None
    dotenv_stub.find_dotenv = lambda *_a, **_k: ''
    monkeypatch.setitem(sys.modules, 'dotenv', dotenv_stub)
    for name in (
        "MASTER_EXCEL_PATH",
        "MASTER_DB_PATH",
        "IMAGE_DIR",
        "SALES_APP_DIR",
        "PRICE_APP_DIR",
        "DEBUG_DIR",
        "OUTPUT_DIR",
        "OUTPUT_EXCEL",
        "OUTPUT_DB",
        "OUTPUT_LOG",
        "LOG_PATH",
        "BASE_REPO_URL",
        "EXTRACTION_GUIDE_PATH",
        "VISION_AGENT_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    importlib.reload(cfg)
    root = Path(__file__).resolve().parent.parent
    assert cfg.MASTER_EXCEL_PATH == root / "Master_data_base" / "master_dataset.xlsx"
    assert cfg.MASTER_DB_PATH == root / "Master_data_base" / "master.db"
    assert cfg.IMAGE_DIR == root / "images"
    assert cfg.SALES_APP_DIR == root / "Sales App" / "sales_app"
    assert cfg.PRICE_APP_DIR == root / "Price App" / "smart_price"
    assert cfg.DEBUG_DIR == root / "LLM_Output_db"
    assert cfg.OUTPUT_DIR == root / "output"
    assert cfg.OUTPUT_EXCEL == root / "output" / "merged_prices.xlsx"
    assert cfg.OUTPUT_DB == root / "output" / "fiyat_listesi.db"
    assert cfg.OUTPUT_LOG == root / "output" / "source_log.csv"
    assert cfg.LOG_PATH == root / "smart_price.log"
    assert cfg.BASE_REPO_URL.endswith("Smart_Price/main")
    assert cfg.DEFAULT_DB_URL == f"{cfg.BASE_REPO_URL}/Master_data_base/master.db"
    assert cfg.DEFAULT_IMAGE_BASE_URL == cfg.BASE_REPO_URL
    assert cfg.EXTRACTION_GUIDE_PATH == root / "extraction_guide.md"


def test_env_and_config_overrides(tmp_path, monkeypatch):
    dotenv_stub = types.ModuleType('dotenv')
    dotenv_stub.load_dotenv = lambda *_a, **_k: None
    dotenv_stub.find_dotenv = lambda *_a, **_k: ''
    monkeypatch.setitem(sys.modules, 'dotenv', dotenv_stub)
    config_path = tmp_path / "config.json"
    config_path.write_text('{"IMAGE_DIR": "imx"}')
    monkeypatch.setattr(cfg, "_REPO_ROOT", tmp_path)
    monkeypatch.setenv("MASTER_EXCEL_PATH", str(tmp_path / "master.xlsx"))
    monkeypatch.setenv("MASTER_DB_PATH", str(tmp_path / "db.sqlite"))
    monkeypatch.setenv("DEBUG_DIR", str(tmp_path / "dbg"))
    monkeypatch.setenv("IMAGE_DIR", str(tmp_path / "img_env"))
    monkeypatch.setenv("SALES_APP_DIR", str(tmp_path / "sales"))
    monkeypatch.setenv("PRICE_APP_DIR", str(tmp_path / "price"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("OUTPUT_EXCEL", str(tmp_path / "out" / "m.xlsx"))
    monkeypatch.setenv("OUTPUT_DB", str(tmp_path / "out" / "db.sqlite"))
    monkeypatch.setenv("OUTPUT_LOG", str(tmp_path / "out" / "log.csv"))
    monkeypatch.setenv("LOG_PATH", str(tmp_path / "custom.log"))
    monkeypatch.setenv("BASE_REPO_URL", "http://example.com/repo")
    monkeypatch.setenv("EXTRACTION_GUIDE_PATH", str(tmp_path / "guide.csv"))
    monkeypatch.setenv("VISION_AGENT_API_KEY", "abc")
    importlib.reload(cfg)
    cfg.load_config()
    assert cfg.MASTER_EXCEL_PATH == tmp_path / "master.xlsx"
    assert cfg.MASTER_DB_PATH == tmp_path / "db.sqlite"
    assert cfg.IMAGE_DIR == tmp_path / "img_env"
    assert cfg.SALES_APP_DIR == tmp_path / "sales"
    assert cfg.PRICE_APP_DIR == tmp_path / "price"
    assert cfg.DEBUG_DIR == tmp_path / "dbg"
    assert cfg.OUTPUT_DIR == tmp_path / "out"
    assert cfg.OUTPUT_EXCEL == tmp_path / "out" / "m.xlsx"
    assert cfg.OUTPUT_DB == tmp_path / "out" / "db.sqlite"
    assert cfg.OUTPUT_LOG == tmp_path / "out" / "log.csv"
    assert cfg.LOG_PATH == tmp_path / "custom.log"
    assert cfg.BASE_REPO_URL == "http://example.com/repo"
    assert cfg.DEFAULT_DB_URL == "http://example.com/repo/Master_data_base/master.db"
    assert cfg.DEFAULT_IMAGE_BASE_URL == "http://example.com/repo"
    assert cfg.EXTRACTION_GUIDE_PATH == tmp_path / "guide.csv"
    assert cfg.VISION_AGENT_API_KEY == "abc"
