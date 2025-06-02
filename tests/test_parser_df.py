import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    import pandas as pd  # noqa: F401
except ModuleNotFoundError:
    pd = None

if pd is not None:
    from smart_price.parsers import parse_df
else:
    parse_df = None


@pytest.mark.skipif(pd is None, reason="pandas not installed")
def test_parse_df_item_name():
    import pandas as pd
    df = pd.DataFrame({"Item Name": ["A1"], "Price": ["10"]})
    result = parse_df(df)
    assert result.iloc[0]["Malzeme_Kodu"] == "A1"
    assert result.iloc[0]["Açıklama"] == "A1"
    assert result.iloc[0]["Fiyat"] == 10.0

