import os
import sqlite3
import sys
import types

_pandas_stubbed = False
try:  # pragma: no cover - pandas may not be installed
    import pandas as pd  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - fallback to stub
    pd = types.ModuleType('pandas')
    sys.modules['pandas'] = pd
    _pandas_stubbed = True
if not hasattr(pd, 'DataFrame'):
    class FakeDF(dict):
        def __init__(self, data=None):
            super().__init__(data or {})
            self.columns = list(self.keys())
        def to_sql(self, name, conn, index=False):
            pass
        def rename(self, columns=None, inplace=False):
            if columns:
                for old, new in columns.items():
                    if old in self:
                        self[new] = self.pop(old)
                self.columns = list(self.keys())
            if not inplace:
                return self
    def _read_sql(query, conn):
        return FakeDF({'material_code': ['X1'], 'description': ['Item']})
    pd.DataFrame = FakeDF
    pd.read_sql = _read_sql
st_stub = sys.modules.get('streamlit', types.ModuleType('streamlit'))
if not hasattr(st_stub, 'cache_data'):
    st_stub.cache_data = lambda *a, **k: (lambda f: f)
sys.modules['streamlit'] = st_stub
if 'requests' not in sys.modules:
    req_stub = types.ModuleType('requests')
    req_stub.get = lambda *_a, **_k: None
    sys.modules['requests'] = req_stub
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
