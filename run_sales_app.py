import os
import pathlib
from streamlit.web import cli as stcli

if __name__ == "__main__":
    pkg_root = pathlib.Path(__file__).parent
    st_file = pkg_root / "sales_app" / "streamlit_app.py"
    stcli.main(["streamlit", "run", str(st_file)])
