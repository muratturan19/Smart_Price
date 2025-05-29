import os
import sys
import types
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Try to import pandas
try:
    import pandas as pd  # noqa: F401
    HAS_PANDAS = hasattr(pd, "DataFrame")
except ModuleNotFoundError:
    HAS_PANDAS = False
    stub = types.ModuleType('pandas')
    stub.DataFrame = type('DataFrame', (), {})
    sys.modules['pandas'] = stub

# Stub optional dependencies
for name in ('pdfplumber', 'tkinter', 'pdf2image', 'pytesseract'):
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)
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

if HAS_PANDAS:
    from smart_price import streamlit_app
else:
    streamlit_app = None


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_save_master_new(tmp_path, monkeypatch):
    pytest.importorskip("openpyxl")
    import pandas as pd

    monkeypatch.chdir(tmp_path)
    df = pd.DataFrame({
        'Malzeme_Kodu': ['A1'],
        'Descriptions': ['Item'],
        'Fiyat': [1.0],
        'Kaynak_Dosya': ['new.xlsx'],
        'Marka': ['BrandA']
    })

    path = streamlit_app.save_master_dataset(df, mode="Yeni fiyat listesi")
    saved = pd.read_excel(path)
    assert len(saved) == 1
    assert saved.iloc[0]['Malzeme_Kodu'] == 'A1'


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_save_master_update(tmp_path, monkeypatch):
    pytest.importorskip("openpyxl")
    import pandas as pd

    monkeypatch.chdir(tmp_path)
    master = pd.DataFrame({
        'Malzeme_Kodu': ['X1', 'Y1'],
        'Descriptions': ['Old', 'Keep'],
        'Fiyat': [2.0, 3.0],
        'Kaynak_Dosya': ['old.xlsx', 'keep.xlsx'],
        'Marka': ['BrandOld', 'BrandKeep'],
        'Yil': [2024, 2024]
    })
    master.to_excel(streamlit_app.get_master_dataset_path(), index=False)

    old_dir = tmp_path / 'LLM_Output_db' / 'old'
    old_dir.mkdir(parents=True)

    new = pd.DataFrame({
        'Malzeme_Kodu': ['Z1'],
        'Descriptions': ['New'],
        'Fiyat': [4.0],
        'Kaynak_Dosya': ['old.xlsx'],
        'Marka': ['BrandOld'],
        'Yil': [2024]
    })

    path = streamlit_app.save_master_dataset(new, mode="Güncelleme")
    result = pd.read_excel(path)
    assert len(result) == 2
    assert 'old.xlsx' not in result[result['Descriptions'] == 'Old']['Kaynak_Dosya'].values
    assert not old_dir.exists()
