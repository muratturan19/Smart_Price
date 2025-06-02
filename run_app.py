import os
import sys
import pathlib

# Ensure a consistent Streamlit configuration when packaged
os.environ["STREAMLIT_SERVER_PORT"] = "8501"
os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
try:
    from dotenv import load_dotenv, find_dotenv
except ImportError:  # pragma: no cover - support missing find_dotenv
    from dotenv import load_dotenv

    def find_dotenv() -> str:
        return ""
from streamlit.web import cli as stcli

load_dotenv(dotenv_path=find_dotenv())

if __name__ == "__main__":
    # When bundled by PyInstaller the application files are extracted to a
    # temporary directory available via ``sys._MEIPASS``.  Using this location
    # ensures the Streamlit script can be found regardless of whether we run
    # from source or from the generated executable.
    base_path = pathlib.Path(getattr(sys, "_MEIPASS", pathlib.Path(__file__).parent))
    pkg_root = base_path
    sys.path.insert(0, str(pkg_root / "Price App"))
    sys.argv = [
        "streamlit",
        "run",
        str(pkg_root / "Price App" / "smart_price" / "streamlit_app.py"),
    ]
    stcli.main()
