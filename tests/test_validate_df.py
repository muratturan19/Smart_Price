import sys

import pandas as pd
from smart_price.core.common_utils import validate_output_df, EXTRACTION_FIELDS


def test_validate_adds_columns_and_normalizes():
    df = pd.DataFrame({"Açıklama": ["Item"], "Fiyat": ["1.000,50"]})
    result = validate_output_df(df)
    assert result.columns.tolist() == EXTRACTION_FIELDS
    assert result.iloc[0]["Fiyat"] == 1000.50
    assert result.iloc[0]["Para_Birimi"] == "₺"


def test_validate_normalizes_currency():
    df = pd.DataFrame({"Açıklama": ["A"], "Fiyat": ["10"], "Para_Birimi": ["usd"]})
    result = validate_output_df(df)
    assert result.iloc[0]["Para_Birimi"] == "$"

