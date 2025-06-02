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
if 'pdf2image' not in sys.modules:
    sys.modules['pdf2image'] = types.ModuleType('pdf2image')
if 'pytesseract' not in sys.modules:
    sys.modules['pytesseract'] = types.ModuleType('pytesseract')
if 'streamlit' not in sys.modules:
    sys.modules['streamlit'] = types.ModuleType('streamlit')
if 'PIL' not in sys.modules:
    pil_stub = types.ModuleType('PIL')
    image_stub = types.ModuleType('PIL.Image')
    class FakeImg:
        pass
    image_stub.Image = FakeImg
    pil_stub.Image = image_stub
    sys.modules['PIL'] = pil_stub
    sys.modules['PIL.Image'] = image_stub

from smart_price.core.common_utils import normalize_price
from smart_price.core.common_utils import detect_brand
from smart_price.core.common_utils import split_code_description
from smart_price.core.common_utils import gpt_clean_text
from smart_price.core.extract_excel import extract_from_excel
from smart_price.core.extract_pdf import extract_from_pdf

if HAS_PANDAS:
    from smart_price import streamlit_app
else:
    streamlit_app = None



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
    assert result["Açıklama"].tolist() == ["Elma", "Armut"]
    expected_cols = [
        "Malzeme_Kodu",
        "Açıklama",
        "Kisa_Kod",
        "Fiyat",
        "Para_Birimi",
        "Marka",
        "Kaynak_Dosya",
        "Record_Code",
        "Ana_Baslik",
        "Alt_Baslik",
    ]
    assert result.columns.tolist() == expected_cols


def test_extract_from_pdf_llm_fallback(monkeypatch):
    if not HAS_PANDAS:
        pytest.skip("pandas not installed")

    class FakePage:
        page_number = 1

        def extract_text(self):
            return ""

        def extract_tables(self):
            return []

    class FakePDF:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

        @property
        def pages(self):
            return [FakePage()]

    def fake_open(_path):
        return FakePDF()

    import sys

    pdfplumber_mod = sys.modules.get("pdfplumber")
    monkeypatch.setattr(pdfplumber_mod, "open", fake_open, raising=False)

    llm_calls = []

    def fake_parse(path, page_range=None):
        llm_calls.append({"path": path, "page_range": page_range})
        import pandas as pd
        return pd.DataFrame({"Malzeme_Kodu": ["X"], "Açıklama": ["ItemZ"], "Fiyat": [55.0]})

    import smart_price.core.extract_pdf as pdf_mod
    monkeypatch.setattr(pdf_mod.ocr_llm_fallback, "parse", fake_parse)

    result = extract_from_pdf("dummy.pdf")
    assert len(result) == 1
    assert result.iloc[0]["Fiyat"] == 55.0
    assert result.iloc[0]["Açıklama"] == "ItemZ"
    assert len(llm_calls) == 1


def test_extract_from_pdf_llm_no_data(monkeypatch):
    if not HAS_PANDAS:
        pytest.skip("pandas not installed")

    class FakePage:
        page_number = 1

        def extract_text(self):
            return ""

        def extract_tables(self):
            return []

    class FakePDF:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

        @property
        def pages(self):
            return [FakePage()]

    def fake_open(_path):
        return FakePDF()

    import sys

    pdfplumber_mod = sys.modules.get("pdfplumber")
    monkeypatch.setattr(pdfplumber_mod, "open", fake_open, raising=False)

    import smart_price.core.extract_pdf as pdf_mod
    monkeypatch.setattr(pdf_mod.ocr_llm_fallback, "parse", lambda *_args, **_kw: pd.DataFrame())

    result = extract_from_pdf("dummy.pdf")
    assert result.empty


def test_extract_from_pdf_llm_only(monkeypatch):
    if not HAS_PANDAS:
        pytest.skip("pandas not installed")

    class FakePage:
        page_number = 1

        def extract_text(self):
            return "ItemA 10"

        def extract_tables(self):
            return []

    class FakePDF:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

        @property
        def pages(self):
            return [FakePage()]

    def fake_open(_path):
        return FakePDF()

    called = {}

    def fake_parse(path, page_range=None):
        called['path'] = path
        import pandas as pd
        return pd.DataFrame({"Açıklama": ["A"], "Fiyat": [1.0]})

    import sys

    pdfplumber_mod = sys.modules.get("pdfplumber")
    monkeypatch.setattr(pdfplumber_mod, "open", fake_open, raising=False)
    import smart_price.core.extract_pdf as pdf_mod
    monkeypatch.setattr(pdf_mod.ocr_llm_fallback, "parse", fake_parse)

    df = extract_from_pdf("dummy.pdf")

    assert not df.empty
    assert called.get('path') == "dummy.pdf"


def test_extract_from_excel_xls(tmp_path):
    if not HAS_PANDAS:
        pytest.skip("pandas not installed")
    pytest.importorskip("xlrd")
    pytest.importorskip("xlwt")
    import pandas as pd

    df = pd.DataFrame({"Ürün Adı": ["Elma"], "Fiyat": ["1.000,50"]})
    file = tmp_path / "sample.xls"
    df.to_excel(file, index=False)

    result = extract_from_excel(str(file))
    assert len(result) == 1
    assert result.iloc[0]["Fiyat"] == 1000.50
    assert result["Açıklama"].tolist() == ["Elma"]


def test_extract_from_excel_code_only(tmp_path):
    if not HAS_PANDAS:
        pytest.skip("pandas not installed")
    pytest.importorskip("openpyxl")
    import pandas as pd

    df = pd.DataFrame({"Ürün Kodu": ["C1", "D2"], "Fiyat": ["10", "20"]})
    file = tmp_path / "code_only.xlsx"
    df.to_excel(file, index=False)

    result = extract_from_excel(str(file))
    assert result["Malzeme_Kodu"].tolist() == ["C1", "D2"]
    assert result["Açıklama"].tolist() == ["C1", "D2"]


def test_extract_from_excel_tip_header(tmp_path):
    if not HAS_PANDAS:
        pytest.skip("pandas not installed")
    pytest.importorskip("openpyxl")
    import pandas as pd

    df = pd.DataFrame({"TİP": ["C1", "D2"], "Fiyat": ["10", "20"]})
    file = tmp_path / "tip.xlsx"
    df.to_excel(file, index=False)

    result = extract_from_excel(str(file))
    assert result["Malzeme_Kodu"].tolist() == ["C1", "D2"]
    assert result["Açıklama"].tolist() == ["C1", "D2"]


def test_extract_from_excel_with_titles(tmp_path):
    if not HAS_PANDAS:
        pytest.skip("pandas not installed")
    pytest.importorskip("openpyxl")
    import pandas as pd

    df = pd.DataFrame(
        {
            "Ana Başlık": ["Main"],
            "Alt_Baslik": ["Sub"],
            "Ürün Adı": ["Item"],
            "Fiyat": ["10"],
        }
    )
    file = tmp_path / "titles.xlsx"
    df.to_excel(file, index=False)

    result = extract_from_excel(str(file))
    assert result.iloc[0]["Ana_Baslik"] == "Main"
    assert result.iloc[0]["Alt_Baslik"] == "Sub"


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
    assert result["Açıklama"].tolist() == ["Elma", "Armut"]
    expected_cols = [
        "Malzeme_Kodu",
        "Açıklama",
        "Kisa_Kod",
        "Fiyat",
        "Para_Birimi",
        "Marka",
        "Kaynak_Dosya",
        "Record_Code",
        "Ana_Baslik",
        "Alt_Baslik",
    ]
    assert result.columns.tolist() == expected_cols


def test_extract_from_excel_header_normalization(tmp_path):
    if not HAS_PANDAS:
        pytest.skip("pandas not installed")
    pytest.importorskip("openpyxl")
    import pandas as pd

    df = pd.DataFrame({
        "urun_kodu": ["001"],
        "Ürün_Adı": ["Elma"],
        "Fiyat": ["1.000,50"],
    })
    file = tmp_path / "underscores.xlsx"
    df.to_excel(file, index=False)

    result = extract_from_excel(str(file))
    assert result.iloc[0]["Malzeme_Kodu"] == "001"
    assert result["Açıklama"].tolist() == ["Elma"]

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


def test_detect_brand_from_filename_multi_word():
    assert detect_brand("Omega Motor_list.xlsx") == "Omega Motor"
    assert detect_brand("ACME_Corp-2023.pdf") == "ACME Corp"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("ABC123 Product", ("ABC123", "Product")),
        ("ABC123 / Product", ("ABC123", "Product")),
        ("Product / ABC123", ("ABC123", "Product")),
        ("Product (ABC123)", ("ABC123", "Product")),
        ("(ABC123) Product", ("ABC123", "Product")),
        ("Just Product", (None, "Just Product")),
    ],
)
def test_split_code_description(text, expected):
    assert split_code_description(text) == expected


def test_gpt_clean_text_extracts_first_json():
    sample = "Result:```json\n[{\"a\":1}]```and more"
    assert gpt_clean_text(sample) == '[{"a":1}]'


def test_gpt_clean_text_object():
    txt = "prefix {\"b\":2} suffix {\"c\":3}"
    assert gpt_clean_text(txt) == '{"b":2}'


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
    assert result["Açıklama"].tolist() == ["Elma"]


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
    assert result["Açıklama"].tolist() == ["Elma"]


def test_extract_from_excel_brand_from_filename_multiword(tmp_path):
    if not HAS_PANDAS:
        pytest.skip("pandas not installed")
    pytest.importorskip("openpyxl")
    import pandas as pd

    df = pd.DataFrame({"Ürün Adı": ["Elma"], "Fiyat": ["1.000,50"]})
    file = tmp_path / "Omega Motor_list.xlsx"
    df.to_excel(file, index=False)

    result = extract_from_excel(str(file))
    assert result.iloc[0]["Marka"] == "Omega Motor"
    assert result["Açıklama"].tolist() == ["Elma"]


def test_extract_from_excel_short_code(tmp_path):
    if not HAS_PANDAS:
        pytest.skip("pandas not installed")
    pytest.importorskip("openpyxl")
    import pandas as pd

    df = pd.DataFrame({
        "Ürün Kodu": ["123"],
        "Kısa Kod": ["A1"],
        "Ürün Adı": ["Elma"],
        "Fiyat": ["1.000,50"],
    })
    file = tmp_path / "short.xlsx"
    df.to_excel(file, index=False)

    result = extract_from_excel(str(file))
    assert result.iloc[0]["Kisa_Kod"] == "A1"
    assert result["Açıklama"].tolist() == ["Elma"]


def test_extract_from_excel_short_code_english_header(tmp_path):
    if not HAS_PANDAS:
        pytest.skip("pandas not installed")
    pytest.importorskip("openpyxl")
    import pandas as pd

    df = pd.DataFrame({
        "Product Code": ["001"],
        "Short Code": ["BB"],
        "Product Name": ["Pear"],
        "Price": ["2.500,75"],
    })
    file = tmp_path / "short_en.xlsx"
    df.to_excel(file, index=False)

    result = extract_from_excel(str(file))
    assert result.iloc[0]["Kisa_Kod"] == "BB"
    assert result["Açıklama"].tolist() == ["Pear"]


def test_extract_from_excel_default_currency(tmp_path):
    if not HAS_PANDAS:
        pytest.skip("pandas not installed")
    pytest.importorskip("openpyxl")
    import pandas as pd

    df = pd.DataFrame({"Ürün Adı": ["Elma"], "Fiyat": ["100"]})
    file = tmp_path / "nocur.xlsx"
    df.to_excel(file, index=False)

    result = extract_from_excel(str(file))
    assert result.iloc[0]["Para_Birimi"] == "TL"
    assert result.iloc[0]["Fiyat"] == 100.0
    assert result["Açıklama"].tolist() == ["Elma"]


def test_extract_from_pdf_default_currency(monkeypatch):
    if not HAS_PANDAS:
        pytest.skip("pandas not installed")
    class FakePage:
        page_number = 1

        def extract_text(self):
            return "ItemA    100"

        def extract_tables(self):
            return []

    class FakePDF:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

        @property
        def pages(self):
            return [FakePage()]

    def fake_open(_path):
        return FakePDF()

    import sys

    pdfplumber_mod = sys.modules.get("pdfplumber")
    monkeypatch.setattr(pdfplumber_mod, "open", fake_open, raising=False)

    result = extract_from_pdf("dummy.pdf")
    assert len(result) == 1
    assert result.iloc[0]["Para_Birimi"] == "TL"
    assert result.iloc[0]["Fiyat"] == 100.0
    expected_cols = [
        "Malzeme_Kodu",
        "Açıklama",
        "Kisa_Kod",
        "Fiyat",
        "Para_Birimi",
        "Marka",
        "Kaynak_Dosya",
        "Record_Code",
        "Ana_Baslik",
        "Alt_Baslik",
    ]
    assert result.columns.tolist() == expected_cols


def test_extract_from_pdf_table_headers(monkeypatch):
    if not HAS_PANDAS:
        pytest.skip("pandas not installed")

    table = [
        ["Ürün Adı", "Fiyat"],
        ["Elma", "1.000,50"],
        ["Armut", "2.500,75"],
    ]

    class FakePage:
        page_number = 1

        def extract_text(self):
            return ""

        def extract_tables(self):
            return [table]

    class FakePDF:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

        @property
        def pages(self):
            return [FakePage()]

    def fake_open(_path):
        return FakePDF()

    import sys

    pdfplumber_mod = sys.modules.get("pdfplumber")
    monkeypatch.setattr(pdfplumber_mod, "open", fake_open, raising=False)

    result = extract_from_pdf("dummy.pdf")
    assert len(result) == 2
    assert result.iloc[0]["Fiyat"] == 1000.50
    assert result.iloc[1]["Fiyat"] == 2500.75
    expected_cols = [
        "Malzeme_Kodu",
        "Açıklama",
        "Kisa_Kod",
        "Fiyat",
        "Para_Birimi",
        "Marka",
        "Kaynak_Dosya",
        "Record_Code",
        "Ana_Baslik",
        "Alt_Baslik",
    ]
    assert result.columns.tolist() == expected_cols


def test_extract_from_pdf_bytesio(monkeypatch):
    if not HAS_PANDAS:
        pytest.skip("pandas not installed")
    import io

    class FakePage:
        page_number = 1

        def extract_text(self):
            return "ItemZ    55"

        def extract_tables(self):
            return []

    class FakePDF:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

        @property
        def pages(self):
            return [FakePage()]

    calls = {}

    def fake_open(*args, **kwargs):
        calls["args"] = args
        calls["kwargs"] = kwargs
        return FakePDF()

    import sys

    pdfplumber_mod = sys.modules.get("pdfplumber")
    monkeypatch.setattr(pdfplumber_mod, "open", fake_open, raising=False)

    buf = io.BytesIO(b"pdf")
    logs = []
    result = extract_from_pdf(buf, filename="dummy.pdf", log=logs.append)

    assert len(result) == 1
    assert result.iloc[0]["Fiyat"] == 55.0
    assert calls.get("args") == (buf,)
    assert any("Phase 1 parsed" in m for m in logs)
    assert calls.get("kwargs") == {}


def test_merge_files_casts_to_string(monkeypatch):
    if not HAS_PANDAS:
        pytest.skip("pandas not installed")
    import pandas as pd

    df = pd.DataFrame(
        {
            "Malzeme_Kodu": [1, 2],
            "Açıklama": ["A", "B"],
            "Kisa_Kod": [10, None],
            "Fiyat": [5, 6],
            "Para_Birimi": ["TL", "TL"],
            "Marka": [None, None],
            "Kaynak_Dosya": ["f.xlsx", "f.xlsx"],
        }
    )

    monkeypatch.setattr(streamlit_app, "extract_from_excel_file", lambda *a, **k: df.copy())

    class FakeUpload:
        def __init__(self, name):
            self.name = name

        def read(self):
            return b"data"

    result = streamlit_app.merge_files([FakeUpload("f.xlsx")])

    assert all(isinstance(v, str) for v in result["Kisa_Kod"])
    assert all(isinstance(v, str) for v in result["Malzeme_Kodu"])


def test_merge_files_pdf_called(monkeypatch):
    if not HAS_PANDAS:
        pytest.skip("pandas not installed")
    import pandas as pd

    df = pd.DataFrame(
        {
            "Malzeme_Kodu": ["C1"],
            "Açıklama": ["A"],
            "Kisa_Kod": [None],
            "Fiyat": [5],
            "Para_Birimi": ["TL"],
            "Marka": [None],
            "Kaynak_Dosya": ["f.pdf"],
            "Ana_Baslik": ["M"],
            "Alt_Baslik": ["S"],
        }
    )

    received = {}

    def fake_pdf(*_args, **kwargs):
        received.update(kwargs)
        return df.copy()

    monkeypatch.setattr(streamlit_app, "extract_from_pdf_file", fake_pdf)

    class FakeUpload:
        def __init__(self, name):
            self.name = name

        def read(self):
            return b"data"

    result = streamlit_app.merge_files([FakeUpload("f.pdf")])

    assert received.get("file_name") == "f.pdf"
    assert not result.empty
    assert result.iloc[0]["Ana_Baslik"] == "M"
    assert result.iloc[0]["Alt_Baslik"] == "S"


def test_merge_files_dedup_by_code_and_price(monkeypatch):
    if not HAS_PANDAS:
        pytest.skip("pandas not installed")
    import pandas as pd

    df_map = {
        "f1.xlsx": pd.DataFrame({
            "Malzeme_Kodu": ["X"],
            "Açıklama": ["Item"],
            "Fiyat": [1.0],
            "Kaynak_Dosya": ["f1.xlsx"],
            "Ana_Baslik": ["T1"],
        }),
        "f2.xlsx": pd.DataFrame({
            "Malzeme_Kodu": ["X"],
            "Açıklama": ["Item"],
            "Fiyat": [1.0],
            "Kaynak_Dosya": ["f2.xlsx"],
            "Ana_Baslik": ["T2"],
        }),
        "f3.xlsx": pd.DataFrame({
            "Malzeme_Kodu": ["X"],
            "Açıklama": ["Item"],
            "Fiyat": [2.0],
            "Kaynak_Dosya": ["f3.xlsx"],
            "Ana_Baslik": ["T3"],
        }),
    }

    def fake_extract(_file, *, file_name=None):
        return df_map[file_name].copy()

    monkeypatch.setattr(streamlit_app, "extract_from_excel_file", fake_extract)

    class FakeUpload:
        def __init__(self, name):
            self.name = name

        def read(self):
            return b"data"

    uploads = [FakeUpload(name) for name in df_map]
    result = streamlit_app.merge_files(uploads)

    assert len(result) == 3
    assert list(result["Fiyat"]) == [1.0, 1.0, 2.0]
    assert list(result["Ana_Baslik"]) == ["T1", "T2", "T3"]


def test_llm_debug_files(monkeypatch, tmp_path):
    if not HAS_PANDAS:
        pytest.skip("pandas not installed")

    class FakePage:
        page_number = 1

        def extract_text(self):
            return ""

        def extract_tables(self):
            return []

    class FakePDF:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

        @property
        def pages(self):
            return [FakePage()]

    def fake_open(_path):
        return FakePDF()

    import sys

    pdfplumber_mod = sys.modules.get("pdfplumber")
    monkeypatch.setattr(pdfplumber_mod, "open", fake_open, raising=False)

    import pandas as pd
    import smart_price.core.extract_pdf as pdf_mod

    def fake_parse(path, page_range=None):
        return pd.DataFrame({"Malzeme_Kodu": ["X"], "Açıklama": ["A"], "Fiyat": [1.0]})

    monkeypatch.setattr(pdf_mod.ocr_llm_fallback, "parse", fake_parse)

    monkeypatch.setenv("SMART_PRICE_DEBUG_DIR", str(tmp_path))

    df = extract_from_pdf("dummy.pdf")

    folder = tmp_path / "dummy"

    assert not df.empty
    assert any(p.suffix == ".png" for p in folder.iterdir())
    assert any(p.name.startswith("llm_response") for p in folder.iterdir())


def test_extract_from_pdf_llm_sets_page_added(monkeypatch):
    if not HAS_PANDAS:
        pytest.skip("pandas not installed")

    class FakePage:
        page_number = 1

        def extract_text(self):
            return ""

        def extract_tables(self):
            return []

    class FakePDF:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

        @property
        def pages(self):
            return [FakePage(), FakePage()]

    def fake_open(_path):
        return FakePDF()

    llm_calls = []

    def fake_convert_from_path(path, *args, **kwargs):
        class Img:
            pass

        return [Img(), Img()]

    def fake_ocr(_img):
        return ""

    import sys

    pdfplumber_mod = sys.modules.get("pdfplumber")
    monkeypatch.setattr(pdfplumber_mod, "open", fake_open, raising=False)
    import smart_price.core.extract_pdf as pdf_mod

    def fake_parse(path, page_range=None):
        llm_calls.append({"path": path, "page_range": page_range})
        import pandas as pd
        return pd.DataFrame({"Açıklama": ["X"], "Fiyat": [5.0]})

    monkeypatch.setattr(pdf_mod.ocr_llm_fallback, "parse", fake_parse)

    logs = []
    df = extract_from_pdf("dummy.pdf", log=logs.append)

    assert not df.empty
    assert len(llm_calls) == 1


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_price_parser_db_schema(monkeypatch, tmp_path):
    import pandas as pd
    import sqlite3
    import argparse
    from smart_price import price_parser

    sample_df = pd.DataFrame(
        {
            "Malzeme_Kodu": ["A1"],
            "Açıklama": ["Item"],
            "Fiyat": [10.0],
            "Birim": ["ADET"],
            "Kutu_Adedi": ["5"],
            "Para_Birimi": ["TL"],
            "Kaynak_Dosya": ["src.xlsx"],
            "Sayfa": [1],
            "Image_Path": ["img.png"],
            "Record_Code": ["R1"],
            "Yil": [2024],
            "Marka": ["Brand"],
            "Kategori": ["Cat"],
        }
    )

    monkeypatch.setattr(price_parser, "extract_from_excel", lambda *_args, **_kw: sample_df.copy())
    monkeypatch.setattr(price_parser, "_configure_tesseract", lambda: None)
    monkeypatch.setattr(pd.DataFrame, "to_excel", lambda *a, **k: None)

    args = argparse.Namespace(
        files=[str(tmp_path / "src.xlsx")],
        output=str(tmp_path / "out.xlsx"),
        db=str(tmp_path / "out.db"),
        log=str(tmp_path / "out.csv"),
        show_log=False,
    )
    monkeypatch.setattr(price_parser, "parse_args", lambda: args)

    price_parser.main()

    conn = sqlite3.connect(args.db)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(prices)")
    cols = [r[1] for r in cur.fetchall()]
    assert cols == [
        "material_code",
        "description",
        "price",
        "unit",
        "box_count",
        "price_currency",
        "source_file",
        "source_page",
        "image_path",
        "record_code",
        "year",
        "brand",
        "main_title",
        "sub_title",
        "category",
    ]
    cur.execute("SELECT * FROM prices")
    row = cur.fetchone()
    assert row == (
        "A1",
        "Item",
        10.0,
        "ADET",
        "5",
        "TL",
        "src.xlsx",
        1,
        "img.png",
        "R1",
        2024,
        "Brand",
        None,
        None,
        "Cat",
    )
    conn.close()

