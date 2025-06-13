import sys
import types
import pytest

try:
    import pandas as pd  # noqa: F401
    HAS_PANDAS = hasattr(pd, "DataFrame")
except ModuleNotFoundError:
    HAS_PANDAS = False
    stub = types.ModuleType("pandas")
    stub.DataFrame = type("DataFrame", (), {})
    sys.modules["pandas"] = stub

if HAS_PANDAS:
    from smart_price import streamlit_app
else:
    streamlit_app = None


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_standardize_desc_column():
    import pandas as pd
    df = pd.DataFrame({
        "Detay": ["Item"],
        "Fiyat": [1.0],
        "Malzeme Kodu": ["A1"],
    })
    result = streamlit_app.standardize_column_names(df)
    assert "Açıklama" in result.columns
    assert result["Açıklama"].tolist() == ["Item"]
