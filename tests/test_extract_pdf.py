import os
import sys

# Ensure repo root is on path for package imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.helpers import extract_pdf


def test_esmaksn_pdf_threshold():
    df = extract_pdf.parse("tests/samples/ESMAKSAN_2025_MART.pdf")
    assert len(df) >= 1600
    assert df['Malzeme_Kodu'].notna().mean() >= 0.7
