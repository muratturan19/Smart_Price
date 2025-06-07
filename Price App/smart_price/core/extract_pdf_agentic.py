from __future__ import annotations

import os
import logging
import tempfile
from pathlib import Path
from typing import IO, Optional, Callable

import pandas as pd
import re

try:
    from dotenv import load_dotenv, find_dotenv
except ImportError:  # pragma: no cover - support missing find_dotenv
    from dotenv import load_dotenv  # type: ignore

    def find_dotenv() -> str:
        return ""


try:  # pragma: no cover - allow stub without args
    load_dotenv(dotenv_path=find_dotenv())
except TypeError:  # pragma: no cover
    load_dotenv(dotenv_path=find_dotenv())

from smart_price.extract_excel import _map_columns
from smart_price.core.extract_excel import (
    _norm_header,
    POSSIBLE_CODE_HEADERS,
    POSSIBLE_DESC_HEADERS,
    POSSIBLE_PRICE_HEADERS,
)
from .common_utils import normalize_price, detect_currency, normalize_currency
from .debug_utils import save_debug, set_output_subdir

try:
    from agentic_doc.common import RetryableError as AgenticDocError
    from agentic_doc.parse import parse
    ADE_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency missing
    ADE_AVAILABLE = False

    class AgenticDocError(Exception):
        """Fallback error when ``agentic_doc`` is unavailable."""


logger = logging.getLogger("smart_price")


def extract_from_pdf_agentic(
    filepath: str | IO[bytes],
    *,
    filename: str | None = None,
    log: Optional[Callable[[str, str], None]] = None,
) -> pd.DataFrame:
    """Extract product information from a PDF file using ``agentic_doc``.

    Parameters
    ----------
    filepath : str or file-like object
        Path of the PDF file or an open file handle.
    filename : str, optional
        Explicit file name used when ``filepath`` is a buffer.
    log : callable, optional
        Optional logging callback accepting ``message`` and ``level``.

    Returns
    -------
    pandas.DataFrame
        DataFrame with the same columns as :func:`extract_from_pdf`.

    Notes
    -----
    ``agentic_doc.parse`` returns a list of ``ParsedDocument`` objects.
    This function uses only the first document in that list. When ``filepath``
    is a file-like object, it is written to a temporary PDF before parsing.
    """

    def notify(message: str, level: str = "info") -> None:
        logger.info(message)
        if log:
            try:
                log(message, level)
            except Exception as exc:  # pragma: no cover - log callback errors
                logger.error("log callback failed: %s", exc)

    api_key = os.getenv("VISION_AGENT_API_KEY")
    if api_key:
        os.environ.setdefault("VISION_AGENT_API_KEY", api_key)

    if not ADE_AVAILABLE:
        notify("agentic_doc not installed", "error")
        raise ValueError("agentic_doc not installed")

    src = filename or getattr(filepath, "name", str(filepath))
    notify(f"Processing {src} via agentic_doc")
    ade_debug = bool(os.getenv("ADE_DEBUG"))
    if ade_debug:
        set_output_subdir(Path(src).stem)

    tmp_file: str | None = None
    if isinstance(filepath, (str, bytes, os.PathLike)):
        parse_path = filepath
    else:
        try:
            filepath.seek(0)
        except Exception as exc:
            notify(f"seek failed: {exc}", "warning")
        pdf_bytes = filepath.read()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.write(pdf_bytes)
        tmp.close()
        tmp_file = tmp.name
        parse_path = tmp_file

    try:
        docs = parse(parse_path)  # Agentic-doc 0.2.3+
    except Exception as exc:
        logger.error("ADE failed: %s", exc, exc_info=True)
        raise

    if not docs:
        notify("agentic_doc.parse returned no documents", "warning")
        raise ValueError("AgenticDE empty result")

    notify(f"{src}: parse returned {type(docs).__name__}")
    summary = getattr(docs[0], "page_summary", None)
    if summary is not None:
        notify(f"{src}: page_summary {summary}")

    def _ade_df(doc):
        rows: list[list[str]] = []
        current_header: list[str] | None = None

        for idx, ch in enumerate(doc.chunks, 1):  # chunk_type fark etmeksizin
            text = getattr(ch, "text", "")
            if ade_debug:
                if text:
                    dbg_text = text
                else:
                    dbg_text = " ".join(
                        getattr(g, "text", "") for g in getattr(ch, "grounding", [])
                    )
                save_debug("ade_chunk", idx, f"{ch.chunk_type}: {dbg_text}")
                logger.debug("chunk %d %s: %s", idx, ch.chunk_type, dbg_text)
            for line in text.splitlines():
                cells = [c.strip() for c in re.split(r"\s{2,}|\t", line) if c.strip()]
                if not cells:
                    continue

                norm = [_norm_header(c) for c in cells]
                if (
                    any(h in norm for h in POSSIBLE_CODE_HEADERS)
                    and any(h in norm for h in POSSIBLE_PRICE_HEADERS)
                ):
                    current_header = cells
                    continue

                if current_header and len(cells) >= 3:
                    rows.append(cells[: len(current_header)])

        if not rows:
            return pd.DataFrame()

        return pd.DataFrame(rows, columns=current_header)

    df = pd.concat([_ade_df(d) for d in docs], ignore_index=True)
    if df.empty:
        raise ValueError("AgenticDE tablo bulamadı")

    # Promote first row to header when columns are numeric
    if all(isinstance(c, int) for c in df.columns):
        df.columns = df.iloc[0].str.strip().str.replace(" ", "_")
        df = df.iloc[1:].reset_index(drop=True)

    df = _map_columns(df)

    df["Fiyat"] = df["Fiyat"].apply(normalize_price)
    df["Para_Birimi"] = df.get(
        "Para_Birimi", df["Fiyat"].astype(str).apply(detect_currency)
    )
    df["Para_Birimi"] = df["Para_Birimi"].apply(normalize_currency).fillna("₺")

    page_summary = getattr(docs[0], "page_summary", None)
    if page_summary is not None and hasattr(df, "__dict__"):
        object.__setattr__(df, "page_summary", page_summary)

    token_counts = getattr(docs[0], "token_counts", None)
    if token_counts is not None and hasattr(df, "__dict__"):
        object.__setattr__(df, "token_counts", token_counts)

    if df.empty:
        pages = len(page_summary) if page_summary is not None else 0
        notify(f"{src}: no rows extracted from {pages} pages", "warning")
        if tmp_file:
            try:
                os.remove(tmp_file)
            except Exception as exc:  # pragma: no cover - cleanup errors
                logger.error("temp file cleanup failed: %s", exc)
        raise ValueError("AgenticDE empty result")

    notify(f"agentic_doc returned {len(df)} rows")
    if tmp_file:
        try:
            os.remove(tmp_file)
        except Exception as exc:  # pragma: no cover - cleanup errors
            logger.error("temp file cleanup failed: %s", exc)
    if ade_debug:
        set_output_subdir(None)

    return df
