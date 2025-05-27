import streamlit as st
import pandas as pd
import io
import os
import sys
from pathlib import Path

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


def extract_from_excel_file(file: io.BytesIO) -> pd.DataFrame:
    """Wrapper around :func:`core.extract_excel.extract_from_excel`."""
    return extract_from_excel(file)


def extract_from_pdf_file(file: io.BytesIO) -> pd.DataFrame:
    """Wrapper around :func:`core.extract_pdf.extract_from_pdf`."""
    return extract_from_pdf(file)


def merge_files(uploaded_files):
    extracted = []
    for up_file in uploaded_files:
        name = up_file.name.lower()
        bytes_data = io.BytesIO(up_file.read())
        if name.endswith((".xlsx", ".xls")):
            df = extract_from_excel_file(bytes_data)
        elif name.endswith(".pdf"):
            df = extract_from_pdf_file(bytes_data)
        else:
            continue
        if not df.empty:
            extracted.append(df)

    if not extracted:
        return pd.DataFrame(columns=["Malzeme_Adi", "Fiyat"])

    master = pd.concat(extracted, ignore_index=True)
    master.dropna(subset=["Malzeme_Adi", "Fiyat"], inplace=True)
    master["Malzeme_Adi"] = master["Malzeme_Adi"].astype(str).str.strip().str.upper()
    master = master[master["Malzeme_Adi"] != ""]
    master["Fiyat"] = pd.to_numeric(master["Fiyat"], errors="coerce")
    master.dropna(subset=["Fiyat"], inplace=True)
    master.drop_duplicates(subset=["Malzeme_Adi"], keep="last", inplace=True)
    master = master[master["Fiyat"] > 0.01]
    master.sort_values(by="Malzeme_Adi", inplace=True)
    return master


def upload_page():
    st.header("Fiyat Dosyalarını Yükle")
    files = st.file_uploader("Excel veya PDF dosyalarını seçin", type=["xlsx", "xls", "pdf"], accept_multiple_files=True)
    if not files:
        return
    if st.button("Dosyaları İşle"):
        df = merge_files(files)
        if df.empty:
            st.warning("Dosyalardan veri çıkarılamadı.")
            return
        st.success(f"{len(df)} kayıt bulundu")
        st.dataframe(df)
        if st.button("Master Veriyi Kaydet"):
            df.to_excel("master_dataset.xlsx", index=False)
            st.success("master_dataset.xlsx kaydedildi")


def search_page():
    st.header("Master Veride Ara")
    data_path = get_master_dataset_path()
    if not os.path.exists(data_path):
        st.info("Önce dosya yükleyip master veriyi oluşturmalısınız.")
        return
    master_df = pd.read_excel(data_path)
    query = st.text_input("Malzeme kodu veya adı")
    if query:
        results = master_df[master_df["Malzeme_Adi"].str.contains(query, case=False, na=False)]
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
    cli()
