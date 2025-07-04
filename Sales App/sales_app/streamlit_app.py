"""Streamlit application for querying the master price dataset."""

import os
import logging
import sqlite3
import tempfile

import pandas as pd
import requests
import streamlit as st
from pathlib import Path
import sys
from smart_price.ui_utils import img_to_base64, logo_overlay
from smart_price.config import DEFAULT_DB_URL, DEFAULT_IMAGE_BASE_URL

ROOT = Path(__file__).resolve().parents[2]
left_logo_url = ROOT / "logo" / "dp_Seffaf_logo.PNG"
right_logo_url = ROOT / "logo" / "sadece_dp_seffaf.PNG"


def resource_path(relative: str) -> str:
    """Return absolute path to resource, works for PyInstaller bundles."""
    base_path = getattr(sys, "_MEIPASS", Path(__file__).parent)
    return str(Path(base_path) / relative)


PAGE_IMAGE_EXT = ".jpg"

logger = logging.getLogger("sales_app")


def _load_dataset(url: str) -> pd.DataFrame:
    """Download the SQLite master dataset from ``url``."""
    logger.info("Fetching master data from %s", url)
    resp = requests.get(url)
    resp.raise_for_status()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    try:
        tmp.write(resp.content)
        tmp.close()
        conn = sqlite3.connect(tmp.name)
        df = pd.read_sql("SELECT * FROM prices", conn)
        conn.close()
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    column_map = {
        "material_code": "Malzeme_Kodu",
        "description": "Açıklama",
        "price": "Fiyat",
        "unit": "Birim",
        "box_count": "Kutu_Adedi",
        "price_currency": "Para_Birimi",
        "source_file": "Kaynak_Dosya",
        "source_page": "Sayfa",
        "image_path": "Image_Path",
        "record_code": "Record_Code",
        "year": "Yil",
        "brand": "Marka",
        "main_header": "Ana_Baslik",
        "sub_header": "Alt_Baslik",
        "category": "Kategori",
    }
    df.rename(columns=column_map, inplace=True)
    return df


@st.cache_data(show_spinner=True)
def get_master_dataset() -> pd.DataFrame:
    """Return the master dataset downloaded from GitHub."""
    url = os.getenv("MASTER_DB_URL", DEFAULT_DB_URL)
    try:
        df = _load_dataset(url)
    except Exception as exc:
        logger.error("Failed to fetch master dataset: %s", exc)
        return pd.DataFrame()
    return df


def search_page(df: pd.DataFrame) -> None:
    st.header("Master Veride Ara")
    if df.empty:
        st.error("Veri yüklenemedi.")
        return

    query = st.text_input("Malzeme kodu veya adı")
    keyword = st.text_input("Anahtar kelime")
    brand = (
        st.selectbox("Marka", [""] + sorted(df["Marka"].dropna().unique().tolist()))
        if "Marka" in df.columns
        else ""
    )
    main_header = (
        st.selectbox(
            "Ana Başlık", [""] + sorted(df["Ana_Baslik"].dropna().unique().tolist())
        )
        if "Ana_Baslik" in df.columns
        else ""
    )
    sub_header = (
        st.selectbox(
            "Alt Başlık", [""] + sorted(df["Alt_Baslik"].dropna().unique().tolist())
        )
        if "Alt_Baslik" in df.columns
        else ""
    )
    category = (
        st.selectbox(
            "Ürün grubu", [""] + sorted(df["Kategori"].dropna().unique().tolist())
        )
        if "Kategori" in df.columns
        else ""
    )

    show_imgs = st.checkbox("Satır önizlemelerini göster", value=False)

    if not any([query, keyword, brand, main_header, sub_header, category]):
        st.info("Aramak için kriter girin")
        return

    filtered = df
    if query:
        filtered = filtered[
            filtered["Açıklama"].str.contains(query, case=False, na=False)
            | filtered["Malzeme_Kodu"].str.contains(query, case=False, na=False)
        ]
    if keyword:
        mask = filtered.apply(
            lambda r: r.astype(str).str.contains(keyword, case=False, na=False).any(),
            axis=1,
        )
        filtered = filtered[mask]
    if brand:
        filtered = filtered[filtered["Marka"] == brand]
    if main_header:
        filtered = filtered[filtered["Ana_Baslik"] == main_header]
    if sub_header:
        filtered = filtered[filtered["Alt_Baslik"] == sub_header]
    if category:
        filtered = filtered[filtered["Kategori"] == category]

    st.write(f"{len(filtered)} kayıt bulundu")
    styled = filtered.style.format({"Fiyat": "{:,.2f}"})
    st.dataframe(styled, hide_index=True, use_container_width=True)

    if not filtered.empty:

        def _fmt(idx: int) -> str:
            row = filtered.loc[idx]
            return f"{row['Açıklama']} ({row['Malzeme_Kodu']})"

        selected = st.selectbox(
            "Ürün seç",
            filtered.index,
            format_func=_fmt,
        )
        row = filtered.loc[selected]
        st.metric(
            label="Fiyat", value=f"{row.get('Fiyat')} {row.get('Para_Birimi','')}"
        )
        img_path = row.get("Image_Path") or row.get("image_path")
        base = os.getenv("IMAGE_BASE_URL", DEFAULT_IMAGE_BASE_URL).rstrip("/")
        if base.endswith("/master.db"):
            base = base.rsplit("/", 1)[0]
        if base.endswith("/Master_data_base"):
            base = base.rsplit("/", 1)[0]
        img_url = None
        if isinstance(img_path, str) and img_path:
            img_url = f"{base}/{img_path.lstrip('/')}"
        else:
            record_code = row.get("Record_Code") or row.get("record_code")
            if isinstance(record_code, str) and "|" in record_code:
                parts = record_code.split("|")
                if len(parts) >= 2:
                    folder = parts[0]
                    try:
                        page_num = int(parts[1])
                    except ValueError:
                        page_num = None
                    if page_num is not None:
                        img_url = (
                            f"{base}/LLM_Output_db/{folder}/"
                            f"page_image_page_{page_num:02d}{PAGE_IMAGE_EXT}"
                        )
        if show_imgs and img_url:
            try:
                resp = requests.get(img_url)
                resp.raise_for_status()
                st.image(resp.content)
            except Exception as exc:
                st.error(f"Resim yüklenemedi: {exc}")


def main() -> None:
    st.set_page_config(layout="wide")

    sidebar_logo_b64 = img_to_base64(left_logo_url)
    st.sidebar.markdown(
        f"<img src='data:image/png;base64,{sidebar_logo_b64}' "
        "style='display:block;margin:20px auto 10px;"
        "width:clamp(60px,8vw,85px);' />",
        unsafe_allow_html=True,
    )

    logo_overlay(right_logo_url, tooltip="Delta Proje")

    st.sidebar.title("Smart Price Sales")
    df = get_master_dataset()
    search_page(df)


def cli() -> None:
    """Entry point used by the console script."""
    from streamlit.web import cli as stcli
    import sys

    sys.argv = ["streamlit", "run", __file__]
    stcli.main()


if __name__ == "__main__":
    main()
