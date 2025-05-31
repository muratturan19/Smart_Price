from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv, find_dotenv

# Repository root is two levels up from this file
_REPO_ROOT = Path(__file__).resolve().parent.parent

# Default locations matching the repository layout
_DEFAULT_MASTER_DB_PATH = _REPO_ROOT / "master.db"
_DEFAULT_IMAGE_DIR = _REPO_ROOT / "images"
_DEFAULT_SALES_APP_DIR = _REPO_ROOT / "sales_app"
_DEFAULT_PRICE_APP_DIR = _REPO_ROOT / "smart_price"
_DEFAULT_DEBUG_DIR = _REPO_ROOT / "LLM_Output_db"
_DEFAULT_OUTPUT_DIR = _REPO_ROOT / "output"
_DEFAULT_OUTPUT_EXCEL = _DEFAULT_OUTPUT_DIR / "merged_prices.xlsx"
_DEFAULT_OUTPUT_DB = _DEFAULT_OUTPUT_DIR / "fiyat_listesi.db"
_DEFAULT_OUTPUT_LOG = _DEFAULT_OUTPUT_DIR / "source_log.csv"

# Public configuration variables (will be initialised by ``load_config``)
MASTER_DB_PATH: Path = _DEFAULT_MASTER_DB_PATH
IMAGE_DIR: Path = _DEFAULT_IMAGE_DIR
SALES_APP_DIR: Path = _DEFAULT_SALES_APP_DIR
PRICE_APP_DIR: Path = _DEFAULT_PRICE_APP_DIR
DEBUG_DIR: Path = _DEFAULT_DEBUG_DIR
OUTPUT_DIR: Path = _DEFAULT_OUTPUT_DIR
OUTPUT_EXCEL: Path = _DEFAULT_OUTPUT_EXCEL
OUTPUT_DB: Path = _DEFAULT_OUTPUT_DB
OUTPUT_LOG: Path = _DEFAULT_OUTPUT_LOG

__all__ = [
    "MASTER_DB_PATH",
    "IMAGE_DIR",
    "SALES_APP_DIR",
    "PRICE_APP_DIR",
    "DEBUG_DIR",
    "OUTPUT_DIR",
    "OUTPUT_EXCEL",
    "OUTPUT_DB",
    "OUTPUT_LOG",
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

    global MASTER_DB_PATH, IMAGE_DIR, SALES_APP_DIR, PRICE_APP_DIR, DEBUG_DIR, OUTPUT_DIR, OUTPUT_EXCEL, OUTPUT_DB, OUTPUT_LOG

    MASTER_DB_PATH = _get("MASTER_DB_PATH", _DEFAULT_MASTER_DB_PATH)
    IMAGE_DIR = _get("IMAGE_DIR", _DEFAULT_IMAGE_DIR)
    SALES_APP_DIR = _get("SALES_APP_DIR", _DEFAULT_SALES_APP_DIR)
    PRICE_APP_DIR = _get("PRICE_APP_DIR", _DEFAULT_PRICE_APP_DIR)
    DEBUG_DIR = _get("DEBUG_DIR", _DEFAULT_DEBUG_DIR)

    OUTPUT_DIR = _get("OUTPUT_DIR", _DEFAULT_OUTPUT_DIR)
    OUTPUT_EXCEL = _get("OUTPUT_EXCEL", OUTPUT_DIR / "merged_prices.xlsx")
    OUTPUT_DB = _get("OUTPUT_DB", OUTPUT_DIR / "fiyat_listesi.db")
    OUTPUT_LOG = _get("OUTPUT_LOG", OUTPUT_DIR / "source_log.csv")


# Initialise configuration on import
load_config()
