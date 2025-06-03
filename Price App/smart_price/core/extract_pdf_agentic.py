from __future__ import annotations

import os
import logging
from typing import IO, Optional, Callable

import pandas as pd

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

from .prompt_utils import prompts_for_pdf

logger = logging.getLogger("smart_price")


def extract_from_pdf_agentic(
    filepath: str | IO[bytes], *, filename: str | None = None, log: Optional[Callable[[str, str], None]] = None
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
    This function uses only the first document in that list.
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

    try:
        from agentic_doc.parse import parse
    except Exception as exc:  # pragma: no cover - optional dependency missing
        notify(f"agentic_doc import failed: {exc}", "error")
        return pd.DataFrame()

    src = filename or getattr(filepath, "name", str(filepath))
    notify(f"Processing {src} via agentic_doc")
    guide_prompt = prompts_for_pdf(os.path.basename(src))

    try:
        result = parse(filepath, prompt=guide_prompt)
    except TypeError:
        result = parse(filepath)
    except Exception as exc:
        notify(f"agentic_doc.parse failed: {exc}", "error")
        status = getattr(exc, "status", None) or getattr(exc, "status_code", None)
        response = getattr(exc, "response", None)
        if response is not None:
            status = status or getattr(response, "status", None) or getattr(response, "status_code", None)
            try:
                body = getattr(response, "text", None) or getattr(response, "content", None)
            except Exception:
                body = None
            if body:
                notify(f"response: {body}", "error")
                logger.error("response: %s", body)
        if status is not None:
            notify(f"status code: {status}", "error")
            logger.error("status code: %s", status)
        logger.exception("agentic_doc.parse failed")
        return pd.DataFrame()

    notify(f"{src}: parse returned {type(result).__name__}")
    summary = getattr(result, "page_summary", None)
    if summary is not None:
        notify(f"{src}: page_summary {summary}")

    if isinstance(result, list):
        if result:
            result = result[0]
        else:
            notify("agentic_doc.parse returned no documents", "warning")
            return pd.DataFrame()

    chunks = getattr(result, "chunks", [])
    df = pd.DataFrame(list(chunks) if chunks is not None else [])

    page_summary = getattr(result, "page_summary", None)
    if page_summary is not None and hasattr(df, "__dict__"):
        object.__setattr__(df, "page_summary", page_summary)

    token_counts = getattr(result, "token_counts", None)
    if token_counts is not None and hasattr(df, "__dict__"):
        object.__setattr__(df, "token_counts", token_counts)

    if df.empty:
        pages = len(page_summary) if page_summary is not None else 0
        notify(f"{src}: no rows extracted from {pages} pages", "warning")

    notify(f"agentic_doc returned {len(df)} rows")

    return df
