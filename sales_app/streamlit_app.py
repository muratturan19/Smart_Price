"""Streamlit application for querying the master price dataset."""
import io
import os
import logging

import pandas as pd
import requests
import streamlit as st

logger = logging.getLogger("sales_app")

DEFAULT_DATA_URL = (
    "https://raw.githubusercontent.com/USERNAME/Smart_Price/master/master_dataset.xlsx"
)


def _load_dataset(url: str) -> pd.DataFrame:
    """Download the Excel master dataset from ``url``."""
    logger.info("Fetching master data from %s", url)
    resp = requests.get(url)
    resp.raise_for_status()
    return pd.read_excel(io.BytesIO(resp.content))


@st.cache_data(show_spinner=True)
def get_master_dataset() -> pd.DataFrame:
    """Return the master dataset downloaded from GitHub."""
    url = os.getenv("MASTER_DATA_URL", DEFAULT_DATA_URL)
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
