import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from smart_price import config

project_root = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=project_root)


def init_logging(log_path: str | os.PathLike[str] | None = None, *, level: int | str | None = None) -> logging.Logger:
    """Initialize application logging.

    Parameters
    ----------
    log_path : str or Path, optional
        Path of the log file. If omitted, :data:`config.LOG_PATH` is used.
    Returns
    -------
    logging.Logger
        Configured logger instance.
    """
    root = Path(__file__).resolve().parent.parent
    log_file = Path(log_path or config.LOG_PATH)
    if not log_file.is_absolute():
        log_file = root / log_file
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("smart_price")
    if level is None:
        level = logging.DEBUG if os.getenv("SMART_PRICE_DEBUG") else logging.INFO
    logger.setLevel(level)

    if logger.handlers:
        logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(formatter)
    fh.setLevel(level)
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    ch.setLevel(level)
    logger.addHandler(ch)

    return logger

