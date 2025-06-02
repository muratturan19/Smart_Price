import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from smart_price.core import prompt_utils
from smart_price import config


def test_load_extraction_guide_csv(tmp_path):
    path = tmp_path / "guide.csv"
    path.write_text("pdf,page,prompt\ndummy.pdf,1,HELLO\n")
    data = prompt_utils.load_extraction_guide(str(path))
    assert data == [{"pdf": "dummy.pdf", "page": "1", "prompt": "HELLO"}]


def test_load_extraction_guide_json(tmp_path):
    path = tmp_path / "guide.json"
    path.write_text('[{"pdf":"dummy.pdf","page":2,"prompt":"HI"}]')
    data = prompt_utils.load_extraction_guide(str(path))
    assert data == [{"pdf": "dummy.pdf", "page": 2, "prompt": "HI"}]


def test_load_extraction_guide_bad(tmp_path, monkeypatch):
    path = tmp_path / "bad.csv"
    path.write_text("not,really")
    monkeypatch.setattr(config, "EXTRACTION_GUIDE_PATH", path)
    # parsing should fail and return empty list
    assert prompt_utils.load_extraction_guide() == []


def test_prompts_for_pdf(tmp_path):
    path = tmp_path / "guide.csv"
    path.write_text("pdf,page,prompt\ndummy.pdf,,ALL\ndummy.pdf,2,TWO\n")
    mapping = prompt_utils.prompts_for_pdf("dummy.pdf", str(path))
    assert mapping == {0: "ALL", 2: "TWO"}


def test_prompts_for_pdf_no_match(tmp_path):
    path = tmp_path / "guide.csv"
    path.write_text("pdf,page,prompt\nother.pdf,1,HELLO\n")
    assert prompt_utils.prompts_for_pdf("dummy.pdf", str(path)) is None
