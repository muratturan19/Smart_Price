from __future__ import annotations

import os
import logging
import tempfile
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
from .ocr_llm_fallback import parse as parse_with_openai
from .extract_excel import (
    _norm_header,
    POSSIBLE_CODE_HEADERS,
    POSSIBLE_DESC_HEADERS,
    POSSIBLE_PRICE_HEADERS,
)
from .common_utils import normalize_price, detect_currency, normalize_currency

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
        notify("agentic_doc not installed; using Vision fallback")
        return parse_with_openai(filepath)

    src = filename or getattr(filepath, "name", str(filepath))
    notify(f"Processing {src} via agentic_doc")
    guide_prompt = prompts_for_pdf(os.path.basename(src))

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
        docs = parse(parse_path, prompt=guide_prompt)
    except TypeError:  # pragma: no cover - older agentic_doc versions
        docs = parse(parse_path)
    except AgenticDocError as e:
        logger.warning("ADE failed \u2192 fallback", exc_info=e)
        return parse_with_openai(parse_path)
    except Exception as exc:
        notify(f"agentic_doc.parse failed: {exc}", "error")
        status = getattr(exc, "status", None) or getattr(exc, "status_code", None)
        response = getattr(exc, "response", None)
        if response is not None:
            status = (
                status
                or getattr(response, "status", None)
                or getattr(response, "status_code", None)
            )
            try:
                body = getattr(response, "text", None) or getattr(
                    response, "content", None
                )
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

    if not docs:
        notify("agentic_doc.parse returned no documents", "warning")
        return pd.DataFrame()

    notify(f"{src}: parse returned {type(docs).__name__}")
    summary = getattr(docs[0], "page_summary", None)
    if summary is not None:
        notify(f"{src}: page_summary {summary}")

    df = pd.concat([d.to_dataframe() for d in docs], ignore_index=True)

    # Promote first row to header when columns are numeric and row has values
    if all(isinstance(c, int) for c in df.columns) and df.iloc[0].notna().all():
        df.columns = [str(x).strip().replace(" ", "_") for x in df.iloc[0]]
        df = df.iloc[1:].reset_index(drop=True)

    def _map_columns(df: pd.DataFrame) -> pd.DataFrame:
        norm = [_norm_header(c) for c in df.columns]

        def pick(cands):
            for h in cands:
                if h in norm:
                    return df.columns[norm.index(h)]

        rename = {
            pick(POSSIBLE_CODE_HEADERS): "Malzeme_Kodu",
            pick(POSSIBLE_DESC_HEADERS): "Açıklama",
            pick(POSSIBLE_PRICE_HEADERS): "Fiyat",
        }
        df.rename(columns={k: v for k, v in rename.items() if k}, inplace=True)
        return df

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

    notify(f"agentic_doc returned {len(df)} rows")
    if tmp_file:
        try:
            os.remove(tmp_file)
        except Exception as exc:  # pragma: no cover - cleanup errors
            logger.error("temp file cleanup failed: %s", exc)

    return df
