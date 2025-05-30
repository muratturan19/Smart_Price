"""Streamlit application for querying the master price dataset."""
import io
import os
import logging
import sqlite3
import tempfile

import pandas as pd
import requests
import streamlit as st

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
        filtered = filtered[filtered["Descriptions"].str.contains(query, case=False, na=False) |
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
            return f"{row['Descriptions']} ({row['Malzeme_Kodu']})"

        selected = st.selectbox(
            "Ürün seç",
            filtered.index,
            format_func=_fmt,
        )
        record_code = filtered.loc[selected].get("Record_Code")
        if isinstance(record_code, str) and "|" in record_code:
            parts = record_code.split("|")
            if len(parts) >= 2:
                folder = parts[0]
                try:
                    page_num = int(parts[1])
                except ValueError:
                    page_num = None
                if page_num is not None:
                    base = os.getenv("IMAGE_BASE_URL", DEFAULT_IMAGE_BASE_URL)
                    img_url = (
                        f"{base}/LLM_Output_db/{folder}/"
                        f"page_image_page_{page_num:02d}.png"
                    )
                    try:
                        resp = requests.get(img_url)
                        resp.raise_for_status()
                        st.image(resp.content)
                    except Exception as exc:
                        st.error(f"Resim yüklenemedi: {exc}")


def main() -> None:
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
