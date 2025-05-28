import sys
import pathlib
from streamlit.web import cli as stcli

if __name__ == "__main__":
    pkg_root = pathlib.Path(__file__).parent
    sys.argv = [
        "streamlit",
        "run",
        str(pkg_root / "smart_price" / "streamlit_app.py"),
    ]
    stcli.main()
