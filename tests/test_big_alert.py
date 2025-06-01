import os
import sys
import types

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from smart_price import icons


def _setup_streamlit(monkeypatch):
    captured = {}
    st_stub = types.ModuleType("streamlit")

    def make(level):
        def func(msg, *, unsafe_allow_html=False):
            captured[level] = (msg, unsafe_allow_html)
        return func

    for lvl in ("success", "error", "warning", "info"):
        setattr(st_stub, lvl, make(lvl))

    st_stub.get_option = lambda name: {}

    monkeypatch.setitem(sys.modules, "streamlit", st_stub)

    # Minimal stubs for optional dependencies
    if "pandas" not in sys.modules:
        stub = types.ModuleType("pandas")
        monkeypatch.setitem(sys.modules, "pandas", stub)
    stub = sys.modules["pandas"]
    if not hasattr(stub, "DataFrame"):
        monkeypatch.setattr(stub, "DataFrame", type("DataFrame", (), {}), raising=False)
    for name in ("pdfplumber", "tkinter", "pdf2image", "pytesseract"):
        if name not in sys.modules:
            monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    if "dotenv" not in sys.modules:
        dotenv_stub = types.ModuleType("dotenv")
        dotenv_stub.load_dotenv = lambda *a, **k: None
        dotenv_stub.find_dotenv = lambda *a, **k: ""
        monkeypatch.setitem(sys.modules, "dotenv", dotenv_stub)
    if "PIL" not in sys.modules:
        pil_stub = types.ModuleType("PIL")
        image_stub = types.ModuleType("PIL.Image")
        class FakeImg:
            pass
        image_stub.Image = FakeImg
        pil_stub.Image = image_stub
        monkeypatch.setitem(sys.modules, "PIL", pil_stub)
        monkeypatch.setitem(sys.modules, "PIL.Image", image_stub)

    return captured


def test_big_alert_default_icon(monkeypatch, tmp_path):
    captured = _setup_streamlit(monkeypatch)

    from smart_price.streamlit_app import big_alert

    big_alert("Hello", level="success")
    assert "success" in captured
    msg, allow = captured["success"]
    assert icons.SUCCESS_ICON_B64 in msg
    assert "<div" in msg
    assert "Hello" in msg
    assert allow is True
