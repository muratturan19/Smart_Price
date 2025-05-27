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

import price_parser

clean_price = price_parser.clean_price
extract_from_excel = price_parser.extract_from_excel
extract_from_pdf = price_parser.extract_from_pdf



def test_extract_from_excel_basic(tmp_path):
    if not HAS_PANDAS:
        pytest.skip("pandas not installed")
    pytest.importorskip("openpyxl")
    import pandas as pd

    data = {
        "Code": ["A1", "B2"],
        "Description": ["Elma", "Armut"],
        "Price": ["1.000,50", "2.500,75"],
        "Currency": ["TRY", None],
    }
    df = pd.DataFrame(data)
    file = tmp_path / "price_2023.xlsx"
    df.to_excel(file, index=False)

    result = extract_from_excel(str(file))
    assert list(result.columns) == [
        'material_code','description','price','price_currency','source_file','source_page','year'
    ]
    assert len(result) == 2
    assert result.iloc[0]['price'] == 1000.50
    assert result.iloc[0]['price_currency'] == 'TRY'
    assert result.iloc[0]['year'] == '2023'
    # second row currency default
    assert result.iloc[1]['price_currency'] == '€'

def test_clean_price_various_formats():
    assert clean_price("1.234,56") == 1234.56
    assert clean_price("1,234.56") is None
    assert clean_price("1.234.567,89") == 1234567.89
    assert clean_price("1234,56") == 1234.56
    assert clean_price("$1,234.56") is None
    assert clean_price("1 234,56") == 1234.56
    assert clean_price("not a number") is None
    assert clean_price(None) is None


def test_extract_from_pdf_basic(monkeypatch):
    if not HAS_PANDAS:
        pytest.skip("pandas not installed")
    class DummyPage:
        def __init__(self, text):
            self._text = text

        def extract_text(self):
            return self._text

    class DummyPDF:
        def __init__(self, pages):
            self.pages = pages

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    def dummy_open(path):
        return DummyPDF([
            DummyPage("ABC01 Some product  10 EUR"),
            DummyPage("XYZ02 Another 20"),
        ])

    monkeypatch.setattr(price_parser.pdfplumber, "open", dummy_open, raising=False)

    result = extract_from_pdf("prices_2022.pdf")
    assert list(result.columns) == [
        'material_code','description','price','price_currency','source_file','source_page','year'
    ]
    assert len(result) == 2
    assert result.iloc[0]['price_currency'] == 'EUR'
    assert result.iloc[1]['price_currency'] == '€'
    assert set(result['source_page']) == {1, 2}
    assert set(result['year']) == {'2022'}
