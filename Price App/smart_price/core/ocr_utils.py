import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Tuple

from PIL import Image
import pytesseract

from smart_price.price_parser import _configure_tesseract

logger = logging.getLogger("smart_price")

_tess_ready = False

def _init_tesseract() -> None:
    global _tess_ready
    if not _tess_ready:
        try:
            _configure_tesseract()
        except Exception as exc:  # pragma: no cover - optional failures
            logger.error("Tesseract configuration failed: %s", exc)
        _tess_ready = True

def _detect_lines(img: Image.Image) -> List[Tuple[int, int, int, int]]:
    width, height = getattr(img, "size", (0, 0))
    boxes: List[Tuple[int, int, int, int]] = []
    try:
        if not hasattr(pytesseract, "image_to_data"):
            return []
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        lines: dict[int, List[int]] = {}
        for left, top, w, h, line_no in zip(
            data.get("left", []),
            data.get("top", []),
            data.get("width", []),
            data.get("height", []),
            data.get("line_num", []),
        ):
            box = lines.setdefault(line_no, [left, top, left + w, top + h])
            box[0] = min(box[0], left)
            box[1] = min(box[1], top)
            box[2] = max(box[2], left + w)
            box[3] = max(box[3], top + h)
        boxes = [tuple(v) for k, v in sorted(lines.items(), key=lambda i: i[0])]
    except Exception as exc:  # pragma: no cover - tesseract errors
        logger.error("Line detection failed: %s", exc)
    if not boxes:
        line_h = max(height // 40, 1)
        y = 0
        while y < height:
            boxes.append((0, y, width, min(height, y + line_h)))
            y += line_h
    return boxes

def ocr_page_lines(img: Image.Image, *, lang: str = "tur", workers: int | None = None) -> List[str]:
    """Return OCR text for each line in ``img`` using Tesseract in parallel."""
    _init_tesseract()
    if workers is None:
        workers = max(1, int(os.getenv("SMART_PRICE_OCR_WORKERS", "5")))
    boxes = _detect_lines(img)
    if not boxes:
        return []

    def _ocr(box: Tuple[int, int, int, int]) -> str:
        crop = img.crop(box)
        try:
            return pytesseract.image_to_string(crop, lang=lang).strip()
        except Exception as exc:  # pragma: no cover - OCR errors
            logger.error("OCR failed: %s", exc)
            return ""

    # Baseline sequential timing
    seq_start = time.time()
    for b in boxes:
        _ocr(b)
    seq_dur = time.time() - seq_start

    par_start = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        texts = list(ex.map(_ocr, boxes))
    par_dur = time.time() - par_start

    logger.info(
        "OCR sequential %.2fs vs parallel %.2fs with %d workers",
        seq_dur,
        par_dur,
        workers,
    )
    return texts
