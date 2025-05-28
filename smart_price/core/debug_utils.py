import os
import logging
from pathlib import Path
from typing import Optional

from PIL import Image  # type: ignore

logger = logging.getLogger("smart_price")


def _debug_enabled() -> bool:
    return bool(os.getenv("SMART_PRICE_DEBUG"))


def _debug_dir() -> Path:
    path = Path(os.getenv("SMART_PRICE_DEBUG_DIR", "output_debug"))
    if _debug_enabled():
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as exc:  # pragma: no cover - optional debug failures
            logger.debug("debug dir creation failed: %s", exc)
    return path


def save_debug(prefix: str, page: int, content: str) -> None:
    if not _debug_enabled():
        return
    dir_path = _debug_dir()
    file_path = dir_path / f"{prefix}_page_{page:02d}.txt"
    try:
        with open(file_path, "w", encoding="utf-8") as fh:
            fh.write(content)
    except Exception as exc:  # pragma: no cover - debug file failures
        logger.debug("debug write failed for %s: %s", file_path, exc)


def save_debug_image(prefix: str, page: int, image: Image.Image) -> Optional[Path]:
    """Save ``image`` under the debug directory if debugging is enabled.

    Parameters
    ----------
    prefix : str
        Name prefix for the saved file.
    page : int
        Page number used in the file name.
    image : :class:`PIL.Image.Image`
        Image to save.

    Returns
    -------
    pathlib.Path or None
        Path of the saved image if debugging is on, otherwise ``None``.
    """
    if not _debug_enabled():
        return None

    dir_path = _debug_dir()
    file_path = dir_path / f"{prefix}_page_{page:02d}.png"
    try:
        image.save(file_path, format="PNG")
    except Exception as exc:  # pragma: no cover - debug file failures
        logger.debug("debug image write failed for %s: %s", file_path, exc)
    return file_path
