import os
import logging
from pathlib import Path
from typing import Optional

from PIL import Image  # type: ignore

logger = logging.getLogger("smart_price")

_subdir: Optional[str] = None


def set_output_subdir(name: Optional[str]) -> None:
    """Set the folder name under ``LLM_Output_db`` used for new files."""
    global _subdir
    _subdir = name


def _debug_dir() -> Path:
    root = Path(os.getenv("SMART_PRICE_DEBUG_DIR", "LLM_Output_db"))
    path = root / _subdir if _subdir else root
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover - optional debug failures
        logger.debug("debug dir creation failed: %s", exc)
    return path


def save_debug(prefix: str, page: int, content: str) -> None:
    dir_path = _debug_dir()
    file_path = dir_path / f"{prefix}_page_{page:02d}.txt"
    try:
        with open(file_path, "w", encoding="utf-8") as fh:
            fh.write(content)
    except Exception as exc:  # pragma: no cover - debug file failures
        logger.debug("debug write failed for %s: %s", file_path, exc)


def save_debug_image(prefix: str, page: int, image: Image.Image) -> Optional[Path]:
    """Save ``image`` under the debug directory.

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
        Path of the saved image if it could be written, otherwise ``None``.
    """
    dir_path = _debug_dir()
    file_path = dir_path / f"{prefix}_page_{page:02d}.png"
    try:
        image.save(file_path, format="PNG")
    except Exception as exc:  # pragma: no cover - debug file failures
        logger.debug("debug image write failed for %s: %s", file_path, exc)
    return file_path


def log_row_change(
    file: str,
    step: str,
    before_df,
    after_df,
    *,
    reason: str,
) -> None:
    """Log row counts before and after a transformation."""
    before = len(before_df)
    after = len(after_df)
    dropped = before - after
    logger.debug(
        f"[{file}] {step} sonrası: {after} satır (drop edilen: {dropped} satır)"
    )
    logger.debug(f"[{file}] Drop nedeni: {reason}")
    if dropped > 0:
        try:
            diff = before_df.loc[~before_df.index.isin(after_df.index)]
            logger.debug(
                f"[{file}] Drop edilen ilk 5 satır: {diff.head().to_dict(orient='records')}"
            )
        except Exception as exc:
            logger.debug(f"[{file}] Dropped rows logging failed: {exc}")
