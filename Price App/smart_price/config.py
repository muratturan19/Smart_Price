from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv, find_dotenv

# Repository root is three levels up from this file
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Default locations matching the repository layout
_DEFAULT_MASTER_DB_PATH = _REPO_ROOT / "Master data base" / "master.db"
_DEFAULT_MASTER_EXCEL_PATH = _REPO_ROOT / "Master data base" / "master_dataset.xlsx"
_DEFAULT_IMAGE_DIR = _REPO_ROOT / "images"
_DEFAULT_SALES_APP_DIR = _REPO_ROOT / "Sales App" / "sales_app"
_DEFAULT_PRICE_APP_DIR = _REPO_ROOT / "Price App" / "smart_price"
_DEFAULT_DEBUG_DIR = _REPO_ROOT / "LLM Images"
_DEFAULT_OUTPUT_DIR = _REPO_ROOT / "output"
_DEFAULT_OUTPUT_EXCEL = _DEFAULT_OUTPUT_DIR / "merged_prices.xlsx"
_DEFAULT_OUTPUT_DB = _DEFAULT_OUTPUT_DIR / "fiyat_listesi.db"
_DEFAULT_OUTPUT_LOG = _DEFAULT_OUTPUT_DIR / "source_log.csv"
_DEFAULT_LOG_PATH = _REPO_ROOT / "smart_price.log"
_DEFAULT_TESSERACT_CMD = Path(r"D:\\Program Files\\Tesseract-OCR\\tesseract.exe")
_DEFAULT_TESSDATA_PREFIX = Path(r"D:\\Program Files\\Tesseract-OCR\\tessdata")

# Default remote repository for the public demo data
_DEFAULT_BASE_REPO_URL = (
    "https://raw.githubusercontent.com/USERNAME/Smart_Price/master"
)

# Public configuration variables (will be initialised by ``load_config``)
MASTER_EXCEL_PATH: Path = _DEFAULT_MASTER_EXCEL_PATH
MASTER_DB_PATH: Path = _DEFAULT_MASTER_DB_PATH
IMAGE_DIR: Path = _DEFAULT_IMAGE_DIR
SALES_APP_DIR: Path = _DEFAULT_SALES_APP_DIR
PRICE_APP_DIR: Path = _DEFAULT_PRICE_APP_DIR
DEBUG_DIR: Path = _DEFAULT_DEBUG_DIR
OUTPUT_DIR: Path = _DEFAULT_OUTPUT_DIR
OUTPUT_EXCEL: Path = _DEFAULT_OUTPUT_EXCEL
OUTPUT_DB: Path = _DEFAULT_OUTPUT_DB
OUTPUT_LOG: Path = _DEFAULT_OUTPUT_LOG
LOG_PATH: Path = _DEFAULT_LOG_PATH
TESSERACT_CMD: Path = _DEFAULT_TESSERACT_CMD
TESSDATA_PREFIX: Path = _DEFAULT_TESSDATA_PREFIX
BASE_REPO_URL: str = _DEFAULT_BASE_REPO_URL
DEFAULT_DB_URL: str = f"{BASE_REPO_URL}/master.db"
DEFAULT_IMAGE_BASE_URL: str = BASE_REPO_URL

__all__ = [
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
    "TESSERACT_CMD",
    "TESSDATA_PREFIX",
    "BASE_REPO_URL",
    "DEFAULT_DB_URL",
    "DEFAULT_IMAGE_BASE_URL",
    "load_config",
]


def load_config() -> None:
    """Load configuration from ``.env`` and ``config.json`` if present."""
    dotenv_file = find_dotenv(usecwd=True)
    if dotenv_file:
        load_dotenv(dotenv_file)

    config_file = _REPO_ROOT / "config.json"
    config: dict[str, str] = {}
    if config_file.exists():
        try:
            config = json.loads(config_file.read_text(encoding="utf-8"))
        except Exception:
            config = {}

    def _get(name: str, default: Path) -> Path:
        return Path(os.getenv(name, config.get(name, str(default))))

    def _get_str(name: str, default: str) -> str:
        return os.getenv(name, config.get(name, default))

    global MASTER_EXCEL_PATH, MASTER_DB_PATH, IMAGE_DIR, SALES_APP_DIR, PRICE_APP_DIR, DEBUG_DIR, OUTPUT_DIR, OUTPUT_EXCEL, OUTPUT_DB, OUTPUT_LOG, LOG_PATH, TESSERACT_CMD, TESSDATA_PREFIX, BASE_REPO_URL, DEFAULT_DB_URL, DEFAULT_IMAGE_BASE_URL

    MASTER_EXCEL_PATH = _get("MASTER_EXCEL_PATH", _DEFAULT_MASTER_EXCEL_PATH)
    MASTER_DB_PATH = _get("MASTER_DB_PATH", _DEFAULT_MASTER_DB_PATH)
    IMAGE_DIR = _get("IMAGE_DIR", _DEFAULT_IMAGE_DIR)
    SALES_APP_DIR = _get("SALES_APP_DIR", _DEFAULT_SALES_APP_DIR)
    PRICE_APP_DIR = _get("PRICE_APP_DIR", _DEFAULT_PRICE_APP_DIR)
    DEBUG_DIR = _get("DEBUG_DIR", _DEFAULT_DEBUG_DIR)

    OUTPUT_DIR = _get("OUTPUT_DIR", _DEFAULT_OUTPUT_DIR)
    OUTPUT_EXCEL = _get("OUTPUT_EXCEL", OUTPUT_DIR / "merged_prices.xlsx")
    OUTPUT_DB = _get("OUTPUT_DB", OUTPUT_DIR / "fiyat_listesi.db")
    OUTPUT_LOG = _get("OUTPUT_LOG", OUTPUT_DIR / "source_log.csv")
    LOG_PATH = _get("LOG_PATH", _DEFAULT_LOG_PATH)
    TESSERACT_CMD = _get("TESSERACT_CMD", _DEFAULT_TESSERACT_CMD)
    TESSDATA_PREFIX = _get("TESSDATA_PREFIX", _DEFAULT_TESSDATA_PREFIX)

    BASE_REPO_URL = _get_str("BASE_REPO_URL", _DEFAULT_BASE_REPO_URL)
    DEFAULT_DB_URL = f"{BASE_REPO_URL}/master.db"
    DEFAULT_IMAGE_BASE_URL = BASE_REPO_URL


# Initialise configuration on import
load_config()
