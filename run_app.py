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
    sys.argv = [
        "streamlit",
        "run",
        str(pkg_root / "smart_price" / "streamlit_app.py"),
    ]
    stcli.main()
