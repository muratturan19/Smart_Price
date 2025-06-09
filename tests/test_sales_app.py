import os
import sys
import sqlite3
import types

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
st_stub = sys.modules.get('streamlit', types.ModuleType('streamlit'))
if not hasattr(st_stub, 'cache_data'):
    st_stub.cache_data = lambda *a, **k: (lambda f: f)
sys.modules['streamlit'] = st_stub
from sales_app import streamlit_app


def test_load_dataset_renames(tmp_path, monkeypatch):
    db_file = tmp_path / "data.db"
    df = pd.DataFrame({"material_code": ["X1"], "description": ["Item"]})
    with sqlite3.connect(db_file) as conn:
        df.to_sql("prices", conn, index=False)

    content = db_file.read_bytes()

    class FakeResp:
        def __init__(self, data):
            self.content = data
        def raise_for_status(self):
            pass

    monkeypatch.setattr(streamlit_app.requests, "get", lambda _u: FakeResp(content))

    result = streamlit_app._load_dataset("http://example.com/db")
    assert "Malzeme_Kodu" in result.columns
    assert "Açıklama" in result.columns
