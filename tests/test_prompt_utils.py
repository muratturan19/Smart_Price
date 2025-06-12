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


def test_load_extraction_guide_md(tmp_path):
    path = tmp_path / "guide.md"
    path.write_text("# Guide\n\n## BRAND\nPrompt text\n")
    data = prompt_utils.load_extraction_guide(str(path))
    assert data == [{"pdf": "BRAND", "page": None, "prompt": "Prompt text"}]


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
    assert mapping is not None
    assert mapping[0].startswith(prompt_utils.RAW_HEADER_HINT)
    assert mapping[2].startswith(prompt_utils.RAW_HEADER_HINT)
    assert mapping[0].splitlines()[-1] == "Sonuçları JSON formatında döndür."
    assert mapping[2].splitlines()[-1] == "Sonuçları JSON formatında döndür."


def test_prompts_for_pdf_md(tmp_path):
    path = tmp_path / "guide.md"
    path.write_text("# G\n\n## BRAND\nPrompt\n")
    mapping = prompt_utils.prompts_for_pdf("BRAND_list.pdf", str(path))
    assert mapping is not None
    assert list(mapping.keys()) == [0]
    assert mapping[0].startswith(prompt_utils.RAW_HEADER_HINT)
    assert mapping[0].splitlines()[-1] == "Sonuçları JSON formatında döndür."


def test_prompts_for_pdf_no_match(tmp_path):
    path = tmp_path / "guide.csv"
    path.write_text("pdf,page,prompt\nother.pdf,1,HELLO\n")
    assert prompt_utils.prompts_for_pdf("dummy.pdf", str(path)) is None


def test_parse_md_guide_skips_json_but_continues(tmp_path):
    path = tmp_path / "guide.md"
    path.write_text(
        "# G\n\n## BRAND\n- Inst1\n### Çıktı Formatı\n```json\n{\n  \"foo\": \"bar\"\n}\n```\nSonraki satır"
    )
    data = prompt_utils.load_extraction_guide(str(path))
    assert len(data) == 1
    prompt = data[0]["prompt"]
    assert "foo" not in prompt and "bar" not in prompt
    assert "Inst1" in prompt
    assert "Sonraki satır" in prompt


def test_prompts_append_json_hint(tmp_path):
    path = tmp_path / "guide.csv"
    path.write_text("pdf,page,prompt\ndummy.pdf,,Some instructions\n")
    mapping = prompt_utils.prompts_for_pdf("dummy.pdf", str(path))
    assert mapping is not None
    assert mapping[0].splitlines()[-1] == "Sonuçları JSON formatında döndür."

