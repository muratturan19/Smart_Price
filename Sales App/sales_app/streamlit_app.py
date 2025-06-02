"""Streamlit application for querying the master price dataset."""
import io
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

left_logo_url = (
    "https://raw.githubusercontent.com/muratturan19/Smart_Price/main/logo/dp_Seffaf_logo.PNG"
)
right_logo_url = (
    "https://raw.githubusercontent.com/muratturan19/Smart_Price/main/logo/sadece_dp_seffaf.PNG"
)


def resource_path(relative: str) -> str:
    """Return absolute path to resource, works for PyInstaller bundles."""
    base_path = getattr(sys, "_MEIPASS", Path(__file__).parent)
    return str(Path(base_path) / relative)

from smart_price.config import DEFAULT_DB_URL, DEFAULT_IMAGE_BASE_URL

logger = logging.getLogger("sales_app")




def _load_dataset(url: str) -> pd.DataFrame:
    """Download the SQLite master dataset from ``url``."""
    logger.info("Fetching master data from %s", url)
    resp = requests.get(url)
    resp.raise_for_status()
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        tmp.write(resp.content)
        tmp.flush()
        conn = sqlite3.connect(tmp.name)
        df = pd.read_sql("SELECT * FROM prices", conn)
        conn.close()
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
    brand = st.selectbox("Marka", [""] + sorted(df["Marka"].dropna().unique().tolist())) if "Marka" in df.columns else ""
    year = st.selectbox("Yıl", [""] + sorted(df["Yil"].dropna().unique().tolist())) if "Yil" in df.columns else ""

    filtered = df
    if query:
        filtered = filtered[filtered["Açıklama"].str.contains(query, case=False, na=False) |
                              filtered["Malzeme_Kodu"].str.contains(query, case=False, na=False)]
    if brand:
        filtered = filtered[filtered["Marka"] == brand]
    if year:
        filtered = filtered[filtered["Yil"] == year]

    st.write(f"{len(filtered)} kayıt bulundu")
    st.dataframe(filtered)

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
        img_path = row.get("Image_Path") or row.get("image_path")
        base = os.getenv("IMAGE_BASE_URL", DEFAULT_IMAGE_BASE_URL)
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
                            f"page_image_page_{page_num:02d}.png"
                        )
        if img_url:
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
