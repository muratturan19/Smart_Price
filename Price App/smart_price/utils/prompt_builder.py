# prompt_builder.py – Dynamic prompt assembler for LLM price-list extraction
# Author: Mira – 13 Jun 2025
"""
1. Okur:   extraction_guide.md (kök dizinde)
2. Böl:    global, synonym, generic, brand-specific, fallback
3. Fonksiyon:  get_prompt_for_file(pdf_name) → marka ya da DEFAULT’a göre
               birleşik prompt döndürür.
"""
from __future__ import annotations
import functools, re, unicodedata, os
from pathlib import Path
from typing import Dict, Tuple

def _resolve_guide_path() -> Path:
    """Return extraction guide path using environment and sensible fallbacks."""
    tried: list[Path] = []

    env_path = os.getenv("PRICE_GUIDE_PATH")
    if env_path:
        p = Path(env_path)
        tried.append(p)
        if p.exists():
            return p

    p = Path.cwd() / "extraction_guide.md"
    tried.append(p)
    if p.exists():
        return p

    p = Path(__file__).resolve().parents[2] / "extraction_guide.md"
    tried.append(p)
    if p.exists():
        return p

    hint = ", ".join(str(t) for t in tried)
    raise FileNotFoundError(
        f"extraction_guide.md not found. Tried: {hint}"
    )

GUIDE_PATH = _resolve_guide_path()

class _GuideCache:
    def __init__(self):
        self.global_block = ""
        self.synonym_block = ""
        self.generic_block = ""
        self.brand_blocks: Dict[str, str] = {}
        self.default_block = ""
        self._loaded = False

    def load(self, md_path: Path | None = None):
        if self._loaded:
            return
        if md_path is None:
            md_path = GUIDE_PATH
        if not md_path.exists():
            raise FileNotFoundError(md_path)
        text = md_path.read_text(encoding="utf-8").replace("\r\n", "\n")
        self.global_block   = self._section(text, r"##\s*0[\s\S]+?\n---\n")
        self.synonym_block  = self._section(text, r"##\s*1[\s\S]+?\n---\n")
        self.generic_block  = self._section(text, r"##\s*2[\s\S]+?\n---\n")
        pattern = re.compile(r"###\s*3\.\d+\s+([^\n]+)\n([\s\S]+?)(?=\n###\s*3\.|\n##\s*4\s*·|\Z)")
        for m in pattern.finditer(text):
            self.brand_blocks[m[1].strip()] = m[2].strip()
        self.default_block = self._section(text, r"##\s*4[\s\S]+?\n---\n")
        self._loaded = True

    @staticmethod
    def _section(text: str, pat: str) -> str:
        m = re.search(pat, text, re.MULTILINE)
        return m.group(0).strip() if m else ""

@functools.lru_cache(maxsize=1)
def _guide() -> _GuideCache:
    g = _GuideCache(); g.load(); return g

def _slug(t: str) -> str:
    t = unicodedata.normalize("NFKD", t).encode("ascii","ignore").decode()
    return re.sub(r"[^a-z0-9]", "", t.lower())

def _match_brand(pdf: str, blocks: Dict[str,str]) -> Tuple[str,str]:
    stem = _slug(Path(pdf).stem)
    for brand, body in blocks.items():
        if _slug(brand) in stem:
            return brand, body
    return "DEFAULT", ""

def get_prompt_for_file(pdf_name: str) -> str:
    g = _guide()
    brand, body = _match_brand(pdf_name, g.brand_blocks)
    parts = [
        g.global_block,
        g.synonym_block,
        g.generic_block,
        f"### BRAND OVERRIDES: {brand}\n{body}" if body else "",
        g.default_block if brand == "DEFAULT" else "",
        '## 5 · RETURN STATEMENT TEMPLATE\n'
        'Aşağıdaki yönergeleri izle ve çıktıyı **JSON** formatında, '
        'kök anahtarı "products" olan tek nesne olarak döndür.'
    ]
    return "\n\n".join(filter(None, parts))
