import importlib
from tests.test_big_alert import _setup_streamlit


def test_batch_size_env(monkeypatch):
    _setup_streamlit(monkeypatch)
    monkeypatch.setenv("SP_PROGRESS_BATCH_SIZE", "7")
    import smart_price.streamlit_app as app
    app = importlib.reload(app)
    assert app.BATCH_SIZE == 7

