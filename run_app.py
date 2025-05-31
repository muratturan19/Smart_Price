import os
import sys
import pathlib
try:
    from dotenv import load_dotenv, find_dotenv
except ImportError:  # pragma: no cover - support missing find_dotenv
    from dotenv import load_dotenv

    def find_dotenv() -> str:
        return ""
from streamlit.web import cli as stcli

load_dotenv(dotenv_path=find_dotenv())

if __name__ == "__main__":
    pkg_root = pathlib.Path(__file__).parent
    sys.path.insert(0, str(pkg_root / "Price App"))
    sys.argv = [
        "streamlit",
        "run",
        str(pkg_root / "Price App" / "smart_price" / "streamlit_app.py"),
    ]
    stcli.main()
