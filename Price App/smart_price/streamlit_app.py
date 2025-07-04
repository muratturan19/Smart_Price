import os
import io
import logging
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Callable, Optional, Iterable

import base64
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from smart_price import icons
from smart_price.ui_utils import img_to_base64
from smart_price.core.extract_excel import (
    extract_from_excel,
    _norm_header,
    _NORMALIZED_CODE_HEADERS,
    POSSIBLE_DESC_HEADERS,
    POSSIBLE_PRICE_HEADERS,
)
from smart_price.core.extract_pdf import extract_from_pdf, MIN_CODE_RATIO
from smart_price.core.extract_pdf_agentic import extract_from_pdf_agentic
from smart_price import config
from smart_price.core.logger import init_logging
from smart_price.core.github_upload import upload_folder, delete_github_folder
from smart_price.core.common_utils import normalize_currency, normalize_price

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(dotenv_path=project_root)

ROOT = Path(__file__).resolve().parents[2]
left_logo_url = ROOT / "logo" / "dp_Seffaf_logo.PNG"
right_logo_url = ROOT / "logo" / "sadece_dp_seffaf.PNG"

logger = logging.getLogger("smart_price")

# Number of pages to process before showing progress information
# Can be overridden using the ``SP_PROGRESS_BATCH_SIZE`` environment variable.
BATCH_SIZE = int(os.getenv("SP_PROGRESS_BATCH_SIZE", "5"))


def standardize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Return ``df`` with common column name variants normalised."""
    mapping = {}
    for col in df.columns:
        norm = _norm_header(col)
        if norm in POSSIBLE_PRICE_HEADERS:
            mapping[col] = "Fiyat"
        elif norm in _NORMALIZED_CODE_HEADERS:
            mapping[col] = "Malzeme_Kodu"
        elif norm in POSSIBLE_DESC_HEADERS or any(
            term in norm for term in {"ozellik", "detay", "explanation"}
        ):
            mapping[col] = "Açıklama"
    if mapping:
        df = df.rename(columns=mapping)
    return df


def big_alert(message: str, *, level: str = "info", icon: str | None = None) -> None:
    """Show an alert box styled using the active theme.

    Parameters
    ----------
    message:
        Text to display.
    level:
        One of ``success``, ``error``, ``warning`` or ``info``.  Determines the
        Streamlit feedback function and default icon.
    icon:
        Optional path to an image file.  When not provided, a default base64
        encoded icon from :mod:`smart_price.icons` is used.
    """

    # ``st.success`` and friends used to accept ``unsafe_allow_html`` but this
    # parameter was removed in newer Streamlit versions.  To maintain the custom
    # HTML formatting we always use ``st.markdown``.

    import streamlit as st
    if icon:
        with open(icon, "rb") as img_file:
            icon_b64 = base64.b64encode(img_file.read()).decode("utf-8")
    else:
        icon_b64 = icons.ICONS.get(level, icons.INFO_ICON_B64)

    get_opt = getattr(st, "get_option", lambda _n: None)
    try:
        theme = get_opt("theme") or {}
    except RuntimeError:
        theme = {}
    text_colour = theme.get("textColor", "#262730")
    bg_colour = theme.get("secondaryBackgroundColor", "#F0F2F6")

    html = f"""
        <div style='display:flex;align-items:center;gap:0.5em;padding:0.75em;"
        f"background:{bg_colour};color:{text_colour};border-radius:0.5em;"
        f"font-size:1.1rem;font-weight:600;'>
            <img src='data:image/png;base64,{icon_b64}' style='width:1.5em;height:1.5em;' />
            <span>{message}</span>
        </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def inject_style() -> None:
    """Inject the global CSS used across the application."""
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    html, body, [class*="css"]  {
        font-family: 'Inter', sans-serif;
    }

    .app-header {
        position: relative;
        display: flex;
        justify-content: center;
        align-items: center;
        padding: 0.75rem 1rem;
        background: var(--secondary-background-color);
        border-bottom: 1px solid #ccc;
    }

    .header-title {
        margin: 0;
        font-size: clamp(1.8rem, 3vw, 2.6rem);
        font-weight: 700;
        text-align: center;
    }

    .header-logo {
        height: clamp(70px, 10vw, 100px);
        padding: 0.25rem;
    }

    .header-logo.left {
        position: absolute;
        left: 1rem;
    }

    .header-logo.right {
        position: absolute;
        right: 1rem;
    }

    .card {
        background: linear-gradient(135deg, #ffffff, #f7f7f9);
        border-radius: 8px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        padding: 1rem;
        margin-bottom: 1rem;
    }

    .stButton button, .stDownloadButton button {
        background: #002060;
        color: #fff;
        border: none;
        padding: 0.4rem 1rem;
        border-radius: 6px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .stButton button:hover, .stDownloadButton button:hover {
        background: #013080;
    }

    input, textarea, select {
        border-radius: 4px !important;
        border: 1px solid #ccc !important;
        padding: 0.4rem !important;
    }
    input:focus, textarea:focus, select:focus {
        border-color: #002060 !important;
        box-shadow: 0 0 0 3px rgba(0,32,96,0.2) !important;
    }

    .uploaded-list {
        list-style: none;
        padding-left: 0;
        margin: 0.5rem 0 1rem 0;
    }
    .uploaded-list li {
        background: #fff;
        border-radius: 6px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        padding: 0.5rem;
        margin-bottom: 0.5rem;
        display: flex;
        align-items: center;
    }
    .uploaded-list img {
        height: 40px;
        width: auto;
        margin-right: 0.5rem;
        border-radius: 4px;
    }

    @media (max-width: 768px) {
        .header-title {
            font-size: 1.5rem;
        }
        .header-logo {
            height: 60px;
        }
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)




def _configure_poppler() -> None:
    """Ensure bundled Poppler binaries are on ``PATH``."""
    if shutil.which("pdftoppm"):
        return
    os.environ["PATH"] = os.pathsep.join(
        [str(config.POPPLER_PATH), os.environ.get("PATH", "")]
    )


def resource_path(relative: str) -> str:
    """Return absolute path to resource, works for PyInstaller bundles."""
    base_path = getattr(sys, "_MEIPASS", Path(__file__).parent)
    return str(Path(base_path) / relative)


def get_master_dataset_path() -> str:
    """Return the configured master dataset path."""
    return str(config.MASTER_EXCEL_PATH)


def extract_from_excel_file(
    file: io.BytesIO, *, file_name: str | None = None
) -> pd.DataFrame:
    """Wrapper around :func:`smart_price.core.extract_excel.extract_from_excel`."""
    return extract_from_excel(file, filename=file_name)


def extract_from_pdf_file(
    file: io.BytesIO,
    *,
    file_name: str | None = None,
    status_log: Optional[Callable[[str, str], None]] = None,
    progress_callback: Optional[Callable[[float], None]] = None,
    pages: str | None = None,
    page_range: Iterable[int] | range | None = None,
    method: str = "LLM (Vision)",
) -> pd.DataFrame:
    """Wrapper around :func:`smart_price.core.extract_pdf.extract_from_pdf`.

    Parameters
    ----------
    file:
        PDF data as ``io.BytesIO``.
    file_name:
        Optional file name used for logging/debugging.
    status_log:
        Optional callable used for status updates.
    progress_callback:
        Optional progress callback passed through to PDF extraction.
    pages:
        Page selection string such as ``"1-4"`` or ``"all"``.
    page_range:
        Iterable of page numbers to process. ``None`` processes all pages.
    method:
        Extraction method. When ``"AgenticDE"`` the ``agentic_doc`` pipeline is
        used. Defaults to ``"LLM (Vision)"``.
    """
    if method == "AgenticDE":
        return extract_from_pdf_agentic(
            file,
            filename=file_name,
            log=status_log,
        )
    if pages and page_range is None:
        page_str = pages.strip().lower()
        if page_str != "all":
            try:
                if "-" in page_str:
                    start_s, end_s = page_str.split("-", 1)
                    start = int(start_s)
                    end = int(end_s)
                else:
                    start = int(page_str)
                    end = start
                page_range = range(start, end + 1)
            except ValueError:
                page_range = None
    return extract_from_pdf(
        file,
        filename=file_name,
        log=status_log,
        progress_callback=progress_callback,
        page_range=page_range,
    )


def merge_files(
    uploaded_files,
    *,
    update_status: Optional[Callable[[str, str], None]] = None,
    update_progress: Optional[Callable[[float], None]] = None,
    update_dataframe: Optional[Callable[[pd.DataFrame], None]] = None,
    method: str = "LLM (Vision)",
    pages: str | None = None,
):
    """Extract and merge uploaded files with optional progress callbacks.

    Parameters
    ----------
    update_dataframe:
        Optional callable receiving the merged DataFrame after each file.
    pages:
        Page selection string such as ``"1-5"``. ``None`` processes all pages.
    """
    logger.info("==> BEGIN merge_files count=%s", len(uploaded_files))
    extracted = []
    token_totals: dict[str, dict[str, int]] = {}
    total_rows = 0
    total = len(uploaded_files)
    for idx, up_file in enumerate(uploaded_files, start=1):
        if update_status:
            update_status("Dosya y\u00fckleniyor, l\u00fctfen bekleyin...", "info")
        if update_progress:
            update_progress((idx - 1) / total)
        logger.info("==> FILE %s processing start", up_file.name)

        page_idx = 0
        total_pages: int | None = None
        last_prog = 0.0

        def page_prog(v: float) -> None:
            nonlocal page_idx, total_pages, last_prog, total_rows
            if update_progress:
                update_progress(((idx - 1) + v) / total)
            if v <= last_prog:
                return
            page_idx += 1
            last_prog = v
            if total_pages is None and v:
                try:
                    total_pages = round(1 / v)
                except Exception:
                    total_pages = None
            if page_idx % BATCH_SIZE == 0 or (
                total_pages is not None and page_idx == total_pages
            ):
                st.info(
                    f"\U0001F680 {page_idx} sayfa işlendi, toplam {total_rows} satır bulundu."
                )

        name = up_file.name.lower()
        bytes_data = io.BytesIO(up_file.read())
        if update_status:
            update_status("Veri ay\u0131klan\u0131yor...", "info")
        df = pd.DataFrame()
        try:
            if name.endswith((".xlsx", ".xls")):
                df = extract_from_excel_file(bytes_data, file_name=up_file.name)
            elif name.endswith(".pdf"):
                df = extract_from_pdf_file(
                    bytes_data,
                    file_name=up_file.name,
                    status_log=update_status,
                    progress_callback=page_prog,
                    pages=pages,
                    method=method,
                )
        except Exception as exc:
            logger.exception("Extraction failed for %s", up_file.name)
            if update_status:
                update_status(f"veri çıkarılamadı: {exc}", "error")
            df = pd.DataFrame()

        try:  # pragma: no cover - diagnostic logging
            sample = df.head() if hasattr(df, "head") else (df[:5] if isinstance(df, list) else df)
            if hasattr(sample, "to_dict"):
                sample = sample.to_dict(orient="records")
            logger.warning("[debug] merge_files head for %s: %s", up_file.name, sample)
        except Exception as exc:
            logger.warning("[debug] merge_files head logging failed: %s", exc)

        if df.empty:
            if update_status:
                update_status("veri çıkarılamadı", "warning")
        else:
            extracted.append(df)
            total_rows += len(df)
            tok = getattr(df, "token_counts", None)
            if tok:
                token_totals[up_file.name] = tok
            if update_status:
                update_status(f"{len(df)} kayıt bulundu", "info")
            if update_dataframe:
                try:
                    update_dataframe(pd.concat(extracted, ignore_index=True))
                except Exception:
                    pass

        logger.info("==> FILE %s extraction done rows=%s", up_file.name, len(df))
        page_summary = getattr(df, "page_summary", None)
        if page_summary is not None:
            logger.info("[merge] page_summary=%s", page_summary)
        if update_progress:
            update_progress(idx / total)

    if not extracted:
        return pd.DataFrame(columns=["Açıklama", "Fiyat"])

    if update_progress:
        update_progress(1.0)

    master = pd.concat(extracted, ignore_index=True)
    try:  # pragma: no cover - diagnostic logging
        col = None
        if hasattr(master, "get"):
            col = master.get("Malzeme_Kodu")
        if col is None and "Malzeme_Kodu" in getattr(master, "columns", []):
            col = master["Malzeme_Kodu"]
        sample = None
        if col is not None:
            if hasattr(col, "dropna"):
                col = col.dropna()
            if hasattr(col, "head"):
                col = col.head()
            if hasattr(col, "tolist"):
                sample = col.tolist()
            elif isinstance(col, (list, tuple)):
                sample = list(col)[:5]
            else:
                sample = str(col)
        logger.warning("[debug] merge_files concat Malzeme_Kodu sample: %s", sample)
    except Exception as exc:
        logger.warning("[debug] merge_files concat logging failed: %s", exc)
    master = standardize_column_names(master)
    logger.debug("[merge] Raw merged rows: %d", len(master))
    if "Fiyat" in master.columns:
        master["Fiyat"] = master["Fiyat"].apply(normalize_price)
    else:
        logger.warning("[merge] 'Fiyat' column missing after merge; columns: %s", list(master.columns))
        master["Fiyat"] = pd.NA
    if "Malzeme_Kodu" not in master.columns:
        logger.warning("[merge] 'Malzeme_Kodu' column missing after merge")
        master["Malzeme_Kodu"] = None
    # Diagnostic logging before dropping rows
    logger.warning(f"[merge] DF column names: {master.columns.tolist()}")
    logger.warning(
        f"[merge] DF Malzeme_Kodu sample: "
        f"{master['Malzeme_Kodu'].dropna().head(5).tolist() if 'Malzeme_Kodu' in master.columns else 'COLUMN NOT FOUND'}"
    )
    drop_mask = master[["Malzeme_Kodu", "Fiyat"]].isna().any(axis=1)
    dropped_preview = master[drop_mask].head().to_dict(orient="records")
    before_len = len(master)
    before_master = master.copy()
    master.dropna(subset=["Malzeme_Kodu", "Fiyat"], inplace=True)
    logger.debug(
        "[merge] Filter sonrası: %d satır (drop edilen: %d satır)",
        len(master),
        before_len - len(master),
    )
    if before_len != len(master):
        logger.debug("[merge] Drop nedeni: subset=['Malzeme_Kodu', 'Fiyat']")
        logger.debug("[merge] Drop edilen ilk 5 satır: %s", dropped_preview)
    if master.empty and before_len > 0 and before_master["Malzeme_Kodu"].isna().all():
        sources = (
            before_master.get("Kaynak_Dosya", pd.Series(dtype=str))
            .dropna()
            .unique()
        )
        brands = (
            before_master.get("Marka", pd.Series(dtype=str))
            .dropna()
            .unique()
        )
        logger.warning(
            "[merge] Tüm satırlar 'Malzeme_Kodu' eksikliğinden dolayı atıldı; kaynak=%s marka=%s; ilk satırlar: %s",
            ", ".join(map(str, sources)) or "N/A",
            ", ".join(map(str, brands)) or "N/A",
            dropped_preview,
        )
        summary = getattr(before_master, "page_summary", None)
        if summary is not None:
            logger.warning("[merge] page_summary=%s", summary)
        if update_status:
            update_status(
                "Malzeme_Kodu olmayan satırlar atlandı, sonuç boş",
                "warning",
            )
    if "Açıklama" in master.columns:
        master["Açıklama"] = (
            master["Açıklama"].astype(str).str.strip().str.upper()
        )
        master.sort_values(by="Açıklama", inplace=True)
    else:
        logger.warning("[merge] 'Açıklama' column missing after merge")
        master["Açıklama"] = None
    if "Kisa_Kod" in master.columns:
        master["Kisa_Kod"] = master["Kisa_Kod"].astype(str)
    if "Malzeme_Kodu" in master.columns:
        master["Malzeme_Kodu"] = master["Malzeme_Kodu"].astype(str)
    if "Ana_Baslik" in master.columns:
        master["Ana_Baslik"] = master["Ana_Baslik"].astype(str)
    if "Alt_Baslik" in master.columns:
        master["Alt_Baslik"] = master["Alt_Baslik"].astype(str)
    if update_status:
        update_status(
            f"{len(master)} sat\u0131r ba\u015far\u0131yla bulundu, sonucu kaydetmek i\u00e7in butona bas\u0131n.",
            "success",
        )
    total_tokens = sum(v.get("input", 0) + v.get("output", 0) for v in token_totals.values())
    if hasattr(master, "__dict__"):
        object.__setattr__(master, "token_totals", token_totals)
        object.__setattr__(master, "total_tokens", total_tokens)
    logger.info("==> END merge_files rows=%s", len(master))
    return master


def save_master_dataset(
    df: pd.DataFrame, mode: str = "Yeni fiyat listesi"
) -> tuple[str, str, bool | str]:
    """Save ``df`` into the master dataset file handling update logic.

    Returns a tuple of the Excel path, DB path and an upload result.  The third
    value is ``True`` when the GitHub upload succeeds, otherwise a string with
    the error information.
    """
    excel_path = os.path.abspath(str(config.MASTER_EXCEL_PATH))
    db_path = os.path.abspath(str(config.MASTER_DB_PATH))
    os.makedirs(os.path.dirname(excel_path), exist_ok=True)
    if "Para_Birimi" not in df.columns:
        df["Para_Birimi"] = None
    df["Para_Birimi"] = df["Para_Birimi"].apply(normalize_currency)
    df["Para_Birimi"] = df["Para_Birimi"].fillna("₺")
    existing = pd.DataFrame()
    if os.path.exists(excel_path):
        try:
            existing = pd.read_excel(excel_path)
        except Exception as exc:  # pragma: no cover - read failures
            logger.error("Failed to read master dataset: %s", exc)
            existing = pd.DataFrame()

    if mode == "Güncelleme" and not existing.empty:
        if "Kaynak_Dosya" in df.columns and "Kaynak_Dosya" in existing.columns:
            values = df["Kaynak_Dosya"].dropna().unique()
            if len(values):
                existing = existing[~existing["Kaynak_Dosya"].isin(values)]

        if "Kaynak_Dosya" in df.columns:
            for src in df["Kaynak_Dosya"].dropna().unique():
                folder = (
                    Path(os.getenv("SMART_PRICE_DEBUG_DIR", "LLM_Output_db"))
                    / Path(src).stem
                )
                if folder.exists():
                    try:
                        shutil.rmtree(folder)
                    except Exception as exc:  # pragma: no cover - cleanup failures
                        logger.debug(
                            "LLM output cleanup failed for %s: %s", folder, exc
                        )

    merged = pd.concat([existing, df], ignore_index=True)
    merged.to_excel(excel_path, index=False)

    conn = sqlite3.connect(db_path)
    with conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS prices (
            material_code TEXT,
            description TEXT,
            price REAL,
            unit TEXT,
            box_count TEXT,
            price_currency TEXT,
            source_file TEXT,
            source_page INTEGER,
            image_path TEXT,
            record_code TEXT,
            year INTEGER,
            brand TEXT,
            main_header TEXT,
            sub_header TEXT,
            category TEXT
            )"""
        )
        db_df = merged.copy()
        db_df.rename(
            columns={
                "Malzeme_Kodu": "material_code",
                "Açıklama": "description",
                "Fiyat": "price",
                "Birim": "unit",
                "Kutu_Adedi": "box_count",
                "Para_Birimi": "price_currency",
                "Kaynak_Dosya": "source_file",
                "Sayfa": "source_page",
                "Image_Path": "image_path",
                "Record_Code": "record_code",
                "Yil": "year",
                "Marka": "brand",
                "Ana_Baslik": "main_header",
                "Alt_Baslik": "sub_header",
                "Kategori": "category",
            },
            inplace=True,
        )
        columns = [
            "material_code",
            "description",
            "price",
            "unit",
            "box_count",
            "price_currency",
            "source_file",
            "source_page",
            "image_path",
            "record_code",
            "year",
            "brand",
            "main_header",
            "sub_header",
            "category",
        ]
        for col in columns:
            if col not in db_df.columns:
                db_df[col] = None
        db_df = db_df[columns]
        db_df.to_sql("prices", conn, if_exists="replace", index=False)
    conn.close()

    upload_ok = upload_folder(
        Path(config.MASTER_EXCEL_PATH).parent,
        remote_prefix="Master_data_base",
    )

    if upload_ok:
        upload_result: bool | str = True
    else:
        logger.error("Repository upload failed")
        upload_result = "Upload başarısız"

    return excel_path, db_path, upload_result


def reset_database() -> None:
    """Remove local files and clear GitHub folders."""

    if config.DEBUG_DIR.exists():
        shutil.rmtree(config.DEBUG_DIR, ignore_errors=True)
    if config.MASTER_DB_PATH.exists():
        try:
            config.MASTER_DB_PATH.unlink()
        except Exception:
            pass
    if config.MASTER_EXCEL_PATH.exists():
        try:
            config.MASTER_EXCEL_PATH.unlink()
        except Exception:
            pass

    delete_github_folder("LLM_Output_db")
    delete_github_folder("Master_data_base")


def upload_page():
    st.header("Fiyat Dosyalarını Yükle")
    st.radio(
        "İşlem türü",
        ["Yeni fiyat listesi", "Güncelleme"],
        key="upload_mode",
    )
    method = st.radio(
        "PDF extraction method",
        ["LLM (Vision)", "AgenticDE"],
        key="pdf_method",
    )
    col_mode, col_start, col_end = st.columns([2, 1, 1])
    with col_mode:
        page_mode = st.selectbox(
            "PDF sayfaları",
            ["Tüm sayfalar", "Sayfa aralığı"],
            key="pdf_page_mode",
        )
    pages = None
    start_page = end_page = None
    if page_mode == "Sayfa aralığı":
        with col_start:
            start_page = st.number_input(
                "Başlangıç",
                min_value=1,
                step=1,
                format="%d",
                key="pdf_page_start",
            )
        with col_end:
            end_page = st.number_input(
                "Bitiş",
                min_value=1,
                step=1,
                format="%d",
                key="pdf_page_end",
            )
        pages = f"{int(start_page)}-{int(end_page)}"

    st.markdown(
        "Belirli sayfaları analiz etmek için aralık girin. "
        "Örn: 2–5, sadece bu sayfalar işlenir"
    )

    files = st.file_uploader(
        "Excel veya PDF dosyalarını seçin",
        type=["xlsx", "xls", "pdf"],
        accept_multiple_files=True,
    )
    if not files:
        return

    items: list[str] = []
    for f in files:
        if f.type.startswith("image"):
            data = f.getvalue()
            img_b64 = base64.b64encode(data).decode("utf-8")
            items.append(f"<li><img src='data:{f.type};base64,{img_b64}' alt='{f.name}' /></li>")
            if hasattr(f, "seek"):
                f.seek(0)
        else:
            items.append(f"<li>{f.name}</li>")
    st.markdown("<ul class='uploaded-list'>" + "".join(items) + "</ul>", unsafe_allow_html=True)

    if st.button("Dosyaları İşle"):
        uploaded_list = ", ".join(f.name for f in files)
        with st.spinner("Dosyalar işleniyor..."):
            status_box = st.empty()
            progress_bar = st.progress(0.0)
            df_placeholder = st.empty()

            def show_status(msg: str, level: str = "info") -> None:
                if level == "success":
                    status_box.success(msg)
                elif level == "warning":
                    status_box.warning(msg)
                else:
                    status_box.info(msg)

            try:
                df = merge_files(
                    files,
                    update_status=show_status,
                    update_progress=lambda v: progress_bar.progress(v),
                    update_dataframe=lambda d: df_placeholder.dataframe(d, use_container_width=True),
                    pages=pages,
                    method=method,
                )
            except Exception as exc:
                if method == "AgenticDE":
                    logger.error("ADE failed: %s", exc, exc_info=True)
                    st.error(f"AgenticDE başarısız oldu: {exc}")
                else:
                    st.error(f"LLM extraction failed: {exc}")
                return
        st.info(f"Yüklenen dosyalar: {uploaded_list}")
        if df.empty:
            big_alert("Dosyalardan veri çıkarılamadı.", level="warning")
            return

        st.session_state["processed_df"] = df
        st.metric("Rows", len(df))
        coverage = df["Malzeme_Kodu"].notna().mean()
        st.metric("Code filled %", f"{coverage:.1%}")
        if coverage < MIN_CODE_RATIO:
            big_alert("Low code coverage – OCR/LLM suggested", level="error")
        st.dataframe(df)
        token_total = getattr(df, "total_tokens", None)
        if token_total is not None:
            st.info(f"Toplam Token: {token_total}")
            details = getattr(df, "token_totals", {})
            for fname, vals in details.items():
                st.write(f"{fname}: input {vals.get('input',0)}, output {vals.get('output',0)}")

    if st.session_state.get("processed_df") is not None and st.button(
        "Master Veriyi Kaydet"
    ):
        df = st.session_state.get("processed_df")
        if df is None or df.empty:
            big_alert("Kaydedilecek veri yok.", level="error")
            return
        try:
            with st.spinner("Kaydediliyor..."):
                logger.info("==> BEGIN save_master_dataset")
                excel_path, db_path, upload_result = save_master_dataset(
                    df,
                    mode=st.session_state.get("upload_mode", "Yeni fiyat listesi"),
                )
                logger.info("==> END save_master_dataset")
        except Exception as exc:  # pragma: no cover - UI feedback only
            big_alert(f"Kaydetme hatası: {exc}", level="error")
        else:
            big_alert(
                f"Veriler kaydedildi:\nExcel: {excel_path}\nDB: {db_path}",
                level="success",
            )
            if upload_result is True:
                big_alert("Upload başarılı", level="success")
            else:
                big_alert(str(upload_result), level="error")


def search_page():
    st.header("Master Veride Ara")
    data_path = get_master_dataset_path()
    if not os.path.exists(data_path):
        st.info("Önce dosya yükleyip master veriyi oluşturmalısınız.")
        return
    master_df = pd.read_excel(data_path)
    query = st.text_input("Malzeme kodu veya adı")
    if query:
        results = master_df[
            master_df["Açıklama"].str.contains(query, case=False, na=False)
        ]
        if not results.empty:
            try:
                theme = st.get_option("theme") or {}
            except RuntimeError:
                theme = {}
            header_colour = theme.get("primaryColor", "#002060")

            styled = results.style.set_table_styles(
                {
                    "": {
                        "selector": "th",
                        "props": [
                            ("background-color", header_colour),
                            ("color", "white"),
                        ],
                    }
                }
            )

            st.dataframe(
                styled,
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info("Eşleşme bulunamadı.")


def reset_page():
    st.header("Database Sıfırla")
    if st.button("Sıfırla"):
        try:
            with st.spinner("Sıfırlanıyor..."):
                reset_database()
        except Exception as exc:
            big_alert(f"Hata: {exc}", level="error")
        else:
            big_alert("Veritabanı sıfırlandı", level="success")


PAGES = {
    "📤 Dosya Yükle": upload_page,
    "🔎 Veride Ara": search_page,
    "♻️ Database Sıfırla": reset_page,
}


def main():
    init_logging(config.LOG_PATH)
    _configure_poppler()
    st.set_page_config(layout="wide")

    inject_style()

    left_logo_b64 = img_to_base64(left_logo_url)
    right_logo_b64 = img_to_base64(right_logo_url)

    header_html = f"""
        <header class='app-header'>
            <img src='data:image/png;base64,{left_logo_b64}' class='header-logo left'>
            <h1 class='header-title'>Smart Price</h1>
            <img src='data:image/png;base64,{right_logo_b64}' class='header-logo right'>
        </header>
    """
    st.markdown(header_html, unsafe_allow_html=True)

    st.sidebar.title("Smart Price")

    tab_labels = list(PAGES.keys())
    tabs = st.tabs(tab_labels)
    for tab, label in zip(tabs, tab_labels):
        with tab:
            PAGES[label]()


def cli() -> None:
    """Entry point to launch the Streamlit application."""
    init_logging(config.LOG_PATH)
    _configure_poppler()
    from streamlit.web import cli as stcli

    sys.argv = ["streamlit", "run", __file__]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
