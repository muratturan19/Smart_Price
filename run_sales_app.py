import os
import pathlib
import sys
from streamlit.web import cli as stcli

if __name__ == "__main__":
    pkg_root = pathlib.Path(__file__).parent
    sys.path.insert(0, str(pkg_root / "Sales App"))
    st_file = pkg_root / "Sales App" / "sales_app" / "streamlit_app.py"
    stcli.main(["streamlit", "run", str(st_file)])
