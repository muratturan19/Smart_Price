import os
from dotenv import load_dotenv

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(dotenv_path=project_root)

import streamlit as st
import pandas as pd
import logging
import io
import sys
import pytesseract
import shutil
import sqlite3
from pathlib import Path
from typing import Callable, Optional
import base64

from smart_price import icons

from smart_price.core.extract_excel import extract_from_excel
from smart_price.core.extract_pdf import extract_from_pdf, MIN_CODE_RATIO
from smart_price import config
from smart_price.core.logger import init_logging
from smart_price.core.github_upload import upload_folder, delete_github_folder

logger = logging.getLogger("smart_price")


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

    if icon:
        with open(icon, "rb") as img_file:
            icon_b64 = base64.b64encode(img_file.read()).decode("utf-8")
    else:
        icon_b64 = icons.ICONS.get(level, icons.INFO_ICON_B64)

    try:
        theme = st.get_option("theme") or {}
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


def _configure_tesseract() -> None:
    """Configure pytesseract paths and log available languages.

    ``shutil.which`` is used to locate ``tesseract``.  If ``TESSDATA_PREFIX`` is
    already defined the value is left untouched.  Default Windows paths are only
    applied when detection fails.
    """
    cmd = shutil.which("tesseract")
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
        if "TESSDATA_PREFIX" not in os.environ:
            guess = os.path.join(os.path.dirname(cmd), "tessdata")
            if os.path.isdir(guess):
                os.environ["TESSDATA_PREFIX"] = guess
    else:  # Fallback for Windows bundles/tests
        os.environ.setdefault("TESSDATA_PREFIX", str(config.TESSDATA_PREFIX))
        pytesseract.pytesseract.tesseract_cmd = str(config.TESSERACT_CMD)
    try:
        langs = (
            pytesseract.get_languages(config="")
            if hasattr(pytesseract, "get_languages")
            else []
        )
        logger.info("Available Tesseract languages: %s", langs)
        if "tur" not in langs:
            logger.error(
                "Tesseract language model 'tur' not found. "
                "Please install or copy the model into the tessdata folder."
            )
    except Exception as exc:  # pragma: no cover - unexpected errors
        logger.error("Tesseract language query failed: %s", exc)


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
) -> pd.DataFrame:
    """Wrapper around :func:`smart_price.core.extract_pdf.extract_from_pdf`."""
    return extract_from_pdf(file, filename=file_name, log=status_log)


def merge_files(
    uploaded_files,
    *,
    update_status: Optional[Callable[[str, str], None]] = None,
    update_progress: Optional[Callable[[float], None]] = None,
):
    """Extract and merge uploaded files with optional progress callbacks."""
    extracted = []
    total = len(uploaded_files)
    for idx, up_file in enumerate(uploaded_files, start=1):
        if update_status:
            update_status("Dosya y\u00fckleniyor, l\u00fctfen bekleyin...", "info")
        if update_progress:
            update_progress((idx - 1) / total)

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
                )
        except Exception:
            df = pd.DataFrame()

        if df.empty:
            if update_status:
                update_status("veri çıkarılamadı", "warning")
        else:
            extracted.append(df)
            if update_status:
                update_status(f"{len(df)} kayıt bulundu", "info")

        if update_progress:
            update_progress(idx / total)

    if not extracted:
        return pd.DataFrame(columns=["Descriptions", "Fiyat"])

    if update_progress:
        update_progress(1.0)

    master = pd.concat(extracted, ignore_index=True)
    logger.debug("[merge] Raw merged rows: %d", len(master))
    master["Fiyat"] = pd.to_numeric(master["Fiyat"], errors="coerce")
    drop_mask = master[["Malzeme_Kodu", "Fiyat"]].isna().any(axis=1)
    dropped_preview = master[drop_mask].head().to_dict(orient="records")
    before_len = len(master)
    master.dropna(subset=["Malzeme_Kodu", "Fiyat"], inplace=True)
    logger.debug(
        "[merge] Filter sonrası: %d satır (drop edilen: %d satır)",
        len(master),
        before_len - len(master),
    )
    if before_len != len(master):
        logger.debug("[merge] Drop nedeni: subset=['Malzeme_Kodu', 'Fiyat']")
        logger.debug("[merge] Drop edilen ilk 5 satır: %s", dropped_preview)
    master["Descriptions"] = master["Descriptions"].astype(str).str.strip().str.upper()
    master.sort_values(by="Descriptions", inplace=True)
    if "Kisa_Kod" in master.columns:
        master["Kisa_Kod"] = master["Kisa_Kod"].astype(str)
    if "Malzeme_Kodu" in master.columns:
        master["Malzeme_Kodu"] = master["Malzeme_Kodu"].astype(str)
    if update_status:
        update_status(
            f"{len(master)} sat\u0131r ba\u015far\u0131yla bulundu, sonucu kaydetmek i\u00e7in butona bas\u0131n.",
            "success",
        )
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
    existing = pd.DataFrame()
    if os.path.exists(excel_path):
        try:
            existing = pd.read_excel(excel_path)
        except Exception as exc:  # pragma: no cover - read failures
            logger.error("Failed to read master dataset: %s", exc)
            existing = pd.DataFrame()

    if mode == "Güncelleme" and not existing.empty:
        for col in ("Marka", "Yil", "Kaynak_Dosya"):
            if col in df.columns and col in existing.columns:
                values = df[col].dropna().unique()
                if len(values):
                    existing = existing[~existing[col].isin(values)]

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
            category TEXT
            )"""
        )
        db_df = merged.copy()
        db_df.rename(
            columns={
                "Malzeme_Kodu": "material_code",
                "Descriptions": "description",
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
                "Kategori": "category",
            },
            inplace=True,
        )
        for col in [
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
            "category",
        ]:
            if col not in db_df.columns:
                db_df[col] = None
        db_df = db_df[
            [
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
                "category",
            ]
        ]
        db_df.to_sql("prices", conn, if_exists="replace", index=False)
    conn.close()

    upload_ok = upload_folder(
        Path(config.MASTER_EXCEL_PATH).parent,
        remote_prefix="Master data base",
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
    delete_github_folder("Master data base")


def upload_page():
    st.header("Fiyat Dosyalarını Yükle")
    st.radio(
        "İşlem türü",
        ["Yeni fiyat listesi", "Güncelleme"],
        key="upload_mode",
    )
    files = st.file_uploader(
        "Excel veya PDF dosyalarını seçin",
        type=["xlsx", "xls", "pdf"],
        accept_multiple_files=True,
    )
    if not files:
        return

    if st.button("Dosyaları İşle"):
        uploaded_list = ", ".join(f.name for f in files)
        with st.spinner("Dosyalar işleniyor..."):
            status_box = st.empty()
            progress_bar = st.progress(0.0)

            def show_status(msg: str, level: str = "info") -> None:
                if level == "success":
                    status_box.success(msg)
                elif level == "warning":
                    status_box.warning(msg)
                else:
                    status_box.info(msg)

            df = merge_files(
                files,
                update_status=show_status,
                update_progress=lambda v: progress_bar.progress(v),
            )
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

    if st.session_state.get("processed_df") is not None and st.button(
        "Master Veriyi Kaydet"
    ):
        df = st.session_state.get("processed_df")
        if df is None or df.empty:
            big_alert("Kaydedilecek veri yok.", level="error")
            return
        try:
            with st.spinner("Kaydediliyor..."):
                excel_path, db_path, upload_result = save_master_dataset(
                    df,
                    mode=st.session_state.get("upload_mode", "Yeni fiyat listesi"),
                )
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
            master_df["Descriptions"].str.contains(query, case=False, na=False)
        ]
        if not results.empty:
            try:
                theme = st.get_option("theme") or {}
            except RuntimeError:
                theme = {}
            header_colour = theme.get("primaryColor", "#002060")
            text_colour = theme.get("textColor", "#262730")

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
    _configure_tesseract()
    st.set_page_config(layout="wide")

    header_html = f"""
        <header class='app-header'>
            <img src='{config.BASE_REPO_URL}/logo/dp_logo.png' class='header-logo left'>
            <h1 class='header-title'>Smart Price</h1>
            <img src='{config.BASE_REPO_URL}/logo/delta%20logo%20-150p.png' class='header-logo right'>
        </header>
        <style>
            .app-header {{
                position: relative;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 0.5rem 1rem;
                background: #fff;
                border-bottom: 1px solid #ccc;
            }}
            .header-title {{
                margin: 0;
                font-size: clamp(1.5rem, 2.5vw, 2.2rem);
                font-weight: 600;
            }}
            .header-logo {{
                height: 40px;
            }}
            .left {{
                position: absolute;
                left: 1rem;
            }}
            .right {{
                position: absolute;
                right: 1rem;
            }}
        </style>
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
    _configure_tesseract()
    from streamlit.web import cli as stcli

    sys.argv = ["streamlit", "run", __file__]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
