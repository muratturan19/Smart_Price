import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
import os
import sys
from pathlib import Path

from core.common_utils import normalize_price
from core.extract_excel import find_columns_in_excel


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
    """Extract product name/code and price from an uploaded Excel file."""
    all_data = []
    try:
        xls = pd.ExcelFile(file)
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            if df.empty:
                continue
            product_col, price_col = find_columns_in_excel(df)
            if product_col and price_col:
                sheet_data = df[[product_col, price_col]].copy()
                sheet_data.columns = ["Malzeme_Adi", "Fiyat_Ham"]
                all_data.append(sheet_data)
    except Exception as exc:
        st.error(f"Excel dosyası işlenirken hata: {exc}")
        return pd.DataFrame(columns=["Malzeme_Adi", "Fiyat"])

    if not all_data:
        return pd.DataFrame(columns=["Malzeme_Adi", "Fiyat"])

    combined = pd.concat(all_data, ignore_index=True)
    combined["Fiyat"] = combined["Fiyat_Ham"].apply(normalize_price)
    return combined[["Malzeme_Adi", "Fiyat"]].dropna()


_patterns = [
    re.compile(r"^(.*?)\s{2,}([\d\.,]+)\s*(?:TL|TRY|EUR|USD|\$|€)?$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"([A-Z0-9\-\s/]{5,50})\s+([\d\.,]+)\s*(?:TL|TRY|EUR|USD|\$|€)?", re.IGNORECASE),
    re.compile(r"Item Code:\s*(.*?)\s*Price:\s*([\d\.,]+)", re.IGNORECASE),
    re.compile(r"Ürün No:\s*(.*?)\s*Birim Fiyat:\s*([\d\.,]+)", re.IGNORECASE),
]


def extract_from_pdf_file(file: io.BytesIO) -> pd.DataFrame:
    """Extract product name/code and price from an uploaded PDF file."""
    data = []
    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue
                for line in text.split("\n"):
                    line = line.strip()
                    if len(line) < 5:
                        continue
                    for pattern in _patterns:
                        matches = pattern.findall(line)
                        if not matches:
                            match_obj = pattern.match(line)
                            if match_obj:
                                matches = [match_obj.groups()]
                        for match in matches:
                            if len(match) != 2:
                                continue
                            product_name = re.sub(r"\s{2,}", " ", match[0].strip())
                            price = normalize_price(match[1])
                            if product_name and price is not None:
                                data.append({"Malzeme_Adi": product_name, "Fiyat": price})
    except Exception as exc:
        st.error(f"PDF dosyası işlenirken hata: {exc}")
        return pd.DataFrame(columns=["Malzeme_Adi", "Fiyat"])
    return pd.DataFrame(data)


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


if __name__ == "__main__":
    from streamlit.web import cli as stcli
    sys.argv = ["streamlit", "run", __file__]
    sys.exit(stcli.main())
