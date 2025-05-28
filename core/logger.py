import logging
import os
from pathlib import Path


def init_logging(log_path: str = "smart_price.log", *, level: int | str | None = None) -> logging.Logger:
    """Initialize application logging.

    Parameters
    ----------
    log_path : str, optional
        File name of the log. It will be created in the project root.
    Returns
    -------
    logging.Logger
        Configured logger instance.
    """
    root = Path(__file__).resolve().parent.parent
    log_file = root / log_path
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

