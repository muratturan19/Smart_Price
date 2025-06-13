import sys
import types

from smart_price import config
import smart_price.core.extract_pdf as pdf_mod
from smart_price.core import prompt_utils


class DummyResult:
    empty = True


def _run_extract(tmp_path, guide_content, filename="dummy.pdf"):
    guide_path = tmp_path / "guide.csv"
    guide_path.write_text(guide_content)
    setattr(config, "EXTRACTION_GUIDE_PATH", guide_path)

    captured = {}

    def fake_parse(path, *, output_name=None, prompt=None, page_range=None):
        captured["prompt"] = prompt
        return DummyResult()

    pdf_mod.ocr_llm_fallback.parse = fake_parse
    pdf_mod.upload_folder = lambda *a, **k: None
    pdf_mod.set_output_subdir = lambda *_: None

    pdf_mod.extract_from_pdf(filename)
    return captured.get("prompt")


def test_guide_hit(monkeypatch, tmp_path):
    monkeypatch.setattr(prompt_utils, "get_prompt_for_file", lambda n: "P1")
    prompt = _run_extract(tmp_path, "pdf,page,prompt\ndummy.pdf,1,HELLO\n")
    assert prompt == "P1"


def test_guide_miss(monkeypatch, tmp_path):
    monkeypatch.setattr(prompt_utils, "get_prompt_for_file", lambda n: "P2")
    prompt = _run_extract(tmp_path, "pdf,page,prompt\nother.pdf,1,HELLO\n")
    assert prompt == "P2"
