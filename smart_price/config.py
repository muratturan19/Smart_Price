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

# Public configuration variables (will be initialised by ``load_config``)
MASTER_DB_PATH: Path = _DEFAULT_MASTER_DB_PATH
IMAGE_DIR: Path = _DEFAULT_IMAGE_DIR
SALES_APP_DIR: Path = _DEFAULT_SALES_APP_DIR
PRICE_APP_DIR: Path = _DEFAULT_PRICE_APP_DIR
DEBUG_DIR: Path = _DEFAULT_DEBUG_DIR

__all__ = [
    "MASTER_DB_PATH",
    "IMAGE_DIR",
    "SALES_APP_DIR",
    "PRICE_APP_DIR",
    "DEBUG_DIR",
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

    global MASTER_DB_PATH, IMAGE_DIR, SALES_APP_DIR, PRICE_APP_DIR, DEBUG_DIR

    MASTER_DB_PATH = _get("MASTER_DB_PATH", _DEFAULT_MASTER_DB_PATH)
    IMAGE_DIR = _get("IMAGE_DIR", _DEFAULT_IMAGE_DIR)
    SALES_APP_DIR = _get("SALES_APP_DIR", _DEFAULT_SALES_APP_DIR)
    PRICE_APP_DIR = _get("PRICE_APP_DIR", _DEFAULT_PRICE_APP_DIR)
    DEBUG_DIR = _get("DEBUG_DIR", _DEFAULT_DEBUG_DIR)


# Initialise configuration on import
load_config()
