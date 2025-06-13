from pathlib import Path
import importlib

import smart_price.utils.prompt_builder as pb

def test_matrix_slug():
    prompt = pb.get_prompt_for_file("MATRIX Fiyat Listesi 10.03.25.pdf")
    assert 'Marka = "MATRIX"' in prompt


def test_guide_path_env(monkeypatch, tmp_path):
    guide = tmp_path / "guide.md"
    guide.write_text("## 0\n---\n## 1\n---")
    monkeypatch.setenv("PRICE_GUIDE_PATH", str(guide))
    mod = importlib.reload(pb)
    assert mod.GUIDE_PATH == guide


def test_guide_path_cwd(monkeypatch, tmp_path):
    guide = tmp_path / "extraction_guide.md"
    guide.write_text("## 0\n---")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PRICE_GUIDE_PATH", raising=False)
    mod = importlib.reload(pb)
    assert mod.GUIDE_PATH == guide


def test_guide_path_default(monkeypatch):
    repo_root = Path(__file__).resolve().parent.parent
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("PRICE_GUIDE_PATH", raising=False)
    mod = importlib.reload(pb)
    assert mod.GUIDE_PATH == repo_root / "extraction_guide.md"
