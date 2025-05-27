import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import types
import pytest

# Try to import pandas to see if available
try:
    import pandas as pd  # noqa: F401
    HAS_PANDAS = True
except ModuleNotFoundError:
    HAS_PANDAS = False
    # Provide a minimal stub so price_parser can be imported for clean_price tests
    sys.modules['pandas'] = types.ModuleType('pandas')

# Stub out optional dependencies used during import
if 'pdfplumber' not in sys.modules:
    sys.modules['pdfplumber'] = types.ModuleType('pdfplumber')
if 'tkinter' not in sys.modules:
    tk_stub = types.ModuleType('tkinter')
    tk_stub.filedialog = types.SimpleNamespace()
    tk_stub.simpledialog = types.SimpleNamespace()
    tk_stub.messagebox = types.SimpleNamespace()
    sys.modules['tkinter'] = tk_stub

from core.common_utils import normalize_price
from core.common_utils import detect_brand
from core.extract_excel import extract_from_excel



def test_extract_from_excel_basic(tmp_path):
    if not HAS_PANDAS:
        pytest.skip("pandas not installed")
    pytest.importorskip("openpyxl")
    import pandas as pd

    data = {"Ürün Adı": ["Elma", "Armut"], "Fiyat": ["1.000,50", "2.500,75"]}
    df = pd.DataFrame(data)
    file = tmp_path / "sample.xlsx"
    df.to_excel(file, index=False)

    result = extract_from_excel(str(file))
    assert len(result) == 2
    assert result.iloc[0]["Fiyat"] == 1000.50
    assert result.iloc[1]["Fiyat"] == 2500.75


def test_extract_from_excel_bytesio():
    if not HAS_PANDAS:
        pytest.skip("pandas not installed")
    pytest.importorskip("openpyxl")
    import pandas as pd
    import io

    data = {"Ürün Adı": ["Elma", "Armut"], "Fiyat": ["1.000,50", "2.500,75"]}
    df = pd.DataFrame(data)
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)

    result = extract_from_excel(buffer, filename="sample.xlsx")
    assert len(result) == 2
    assert result.iloc[0]["Fiyat"] == 1000.50
    assert result.iloc[1]["Fiyat"] == 2500.75

def test_normalize_price_various_formats():
    assert normalize_price("1.234,56") == 1234.56
    assert normalize_price("1,234.56", style="en") == 1234.56
    assert normalize_price("1.234.567,89") == 1234567.89
    assert normalize_price("1234,56") == 1234.56
    assert normalize_price("$1,234.56", style="en") == 1234.56
    assert normalize_price("1 234,56") == 1234.56
    assert normalize_price("not a number") is None
    assert normalize_price(None) is None

def test_normalize_price_english_only():
    assert normalize_price("1,234.56", style="en") == 1234.56
    # default EU style should not interpret English numbers
    assert normalize_price("1,234.56") is None


def test_detect_brand_from_filename():
    assert detect_brand("Acme_prices.xlsx") == "Acme"
    assert detect_brand("/path/to/BrandB-2021.pdf") == "BrandB"


def test_extract_from_excel_brand_from_filename(tmp_path):
    if not HAS_PANDAS:
        pytest.skip("pandas not installed")
    pytest.importorskip("openpyxl")
    import pandas as pd

    df = pd.DataFrame({"Ürün Adı": ["Elma"], "Fiyat": ["1.000,50"]})
    file = tmp_path / "Acme_list.xlsx"
    df.to_excel(file, index=False)

    result = extract_from_excel(str(file))
    assert result.iloc[0]["Marka"] == "Acme"


def test_extract_from_excel_brand_filename_param():
    if not HAS_PANDAS:
        pytest.skip("pandas not installed")
    pytest.importorskip("openpyxl")
    import pandas as pd
    import io

    df = pd.DataFrame({"Ürün Adı": ["Elma"], "Fiyat": ["1.000,50"]})
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)

    result = extract_from_excel(buf, filename="BrandX_prices.xlsx")
    assert result.iloc[0]["Marka"] == "BrandX"
