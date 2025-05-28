import os
import sys
import pathlib
from dotenv import load_dotenv
from streamlit.web import cli as stcli

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv(dotenv_path=project_root)

if __name__ == "__main__":
    pkg_root = pathlib.Path(__file__).parent
    sys.argv = [
        "streamlit",
        "run",
        str(pkg_root / "smart_price" / "streamlit_app.py"),
    ]
    stcli.main()
