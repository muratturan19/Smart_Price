import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from utils.prompt_builder import get_prompt_for_file

def test_matrix_slug():
    prompt = get_prompt_for_file("MATRIX Fiyat Listesi 10.03.25.pdf")
    assert 'Marka = "MATRIX"' in prompt
