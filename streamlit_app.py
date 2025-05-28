import streamlit as st
import pandas as pd
import io
import os
import sys
from pathlib import Path
from typing import Callable, Optional

from core.extract_excel import extract_from_excel
from core.extract_pdf import extract_from_pdf


def resource_path(relative: str) -> str:
    """Return absolute path to resource, works for PyInstaller bundles."""
    base_path = getattr(sys, '_MEIPASS', Path(__file__).parent)
    return str(Path(base_path) / relative)


DATA_FILE = "master_dataset.xlsx"


def get_master_dataset_path() -> str:
    """Locate master dataset either next to the executable or inside bundle."""
    if os.path.exists(DATA_FILE):
        return DATA_FILE
    bundled = resource_path(DATA_FILE)
    if os.path.exists(bundled):
        return bundled
    return DATA_FILE


def extract_from_excel_file(
    file: io.BytesIO, *, file_name: str | None = None
) -> pd.DataFrame:
    """Wrapper around :func:`core.extract_excel.extract_from_excel`."""
    return extract_from_excel(file, filename=file_name)


def extract_from_pdf_file(
    file: io.BytesIO,
    *,
    file_name: str | None = None,
    status_log: Optional[Callable[[str], None]] = None,
) -> pd.DataFrame:
    """Wrapper around :func:`core.extract_pdf.extract_from_pdf`."""
    return extract_from_pdf(file, filename=file_name, log=status_log)


def merge_files(
    uploaded_files,
    *,
    update_status: Optional[Callable[[str], None]] = None,
    update_progress: Optional[Callable[[float], None]] = None,
):
    """Extract and merge uploaded files with optional progress callbacks."""
    extracted = []
    total = len(uploaded_files)
    for idx, up_file in enumerate(uploaded_files, start=1):
        if update_status:
            update_status(f"{up_file.name} okunuyor")
        if update_progress:
            update_progress((idx - 1) / total)

        name = up_file.name.lower()
        bytes_data = io.BytesIO(up_file.read())
        df = pd.DataFrame()
        try:
            if name.endswith((".xlsx", ".xls")):
                df = extract_from_excel_file(bytes_data, file_name=up_file.name)
            elif name.endswith(".pdf"):
                df = extract_from_pdf_file(
                    bytes_data, file_name=up_file.name, status_log=update_status
                )
        except Exception:
            df = pd.DataFrame()

        if df.empty:
            if update_status:
                update_status("veri çıkarılamadı")
        else:
            extracted.append(df)
            if update_status:
                update_status(f"{len(df)} kayıt bulundu")

        if update_progress:
            update_progress(idx / total)

    if not extracted:
        return pd.DataFrame(columns=["Descriptions", "Fiyat"])

    if update_progress:
        update_progress(1.0)
    if update_status:
        update_status("Tamamlandı")

    master = pd.concat(extracted, ignore_index=True)
    master.dropna(subset=["Descriptions", "Fiyat"], inplace=True)
    master["Descriptions"] = master["Descriptions"].astype(str).str.strip().str.upper()
    master = master[master["Descriptions"] != ""]
    master["Fiyat"] = pd.to_numeric(master["Fiyat"], errors="coerce")
    master.dropna(subset=["Fiyat"], inplace=True)
    master.drop_duplicates(subset=["Descriptions"], keep="last", inplace=True)
    master = master[master["Fiyat"] > 0.01]
    master.sort_values(by="Descriptions", inplace=True)
    if "Kisa_Kod" in master.columns:
        master["Kisa_Kod"] = master["Kisa_Kod"].astype(str)
    if "Malzeme_Kodu" in master.columns:
        master["Malzeme_Kodu"] = master["Malzeme_Kodu"].astype(str)
    return master


def upload_page():
    st.header("Fiyat Dosyalarını Yükle")
    files = st.file_uploader("Excel veya PDF dosyalarını seçin", type=["xlsx", "xls", "pdf"], accept_multiple_files=True)
    if not files:
        return
    if st.button("Dosyaları İşle"):
        status = st.empty()
        progress_bar = st.progress(0.0)
        df = merge_files(
            files,
            update_status=status.write,
            update_progress=lambda v: progress_bar.progress(v),
        )
        if df.empty:
            st.warning("Dosyalardan veri çıkarılamadı.")
            return
        st.success(f"{len(df)} kayıt bulundu")
        st.dataframe(df)
        if st.button("Master Veriyi Kaydet"):
            data_path = os.path.abspath(get_master_dataset_path())
            try:
                df.to_excel(data_path, index=False)
            except Exception as exc:  # pragma: no cover - UI feedback only
                st.error(f"Kaydetme hatası: {exc}")
            else:
                st.success(f"{data_path} konumuna kaydedildi")


def search_page():
    st.header("Master Veride Ara")
    data_path = get_master_dataset_path()
    if not os.path.exists(data_path):
        st.info("Önce dosya yükleyip master veriyi oluşturmalısınız.")
        return
    master_df = pd.read_excel(data_path)
    query = st.text_input("Malzeme kodu veya adı")
    if query:
        results = master_df[master_df["Descriptions"].str.contains(query, case=False, na=False)]
        st.write(results)


PAGES = {
    "Dosya Yükle": upload_page,
    "Veride Ara": search_page,
}


def main():
    st.sidebar.title("Smart Price")
    choice = st.sidebar.radio("Seçim", list(PAGES.keys()))
    page = PAGES[choice]
    page()


def cli() -> None:
    """Entry point to launch the Streamlit application."""
    from streamlit.web import cli as stcli
    sys.argv = ["streamlit", "run", __file__]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
