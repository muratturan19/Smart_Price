from __future__ import annotations

import os
import tempfile
from typing import IO, Any, Optional, Sequence, Callable
import logging
from datetime import datetime
import difflib
import unicodedata

import pandas as pd

try:
    from dotenv import load_dotenv, find_dotenv
except ImportError:  # pragma: no cover - support missing find_dotenv
    from dotenv import load_dotenv

    def find_dotenv() -> str:
        return ""


try:
    load_dotenv(dotenv_path=find_dotenv())
except TypeError:  # pragma: no cover - allow stub without args
    load_dotenv(dotenv_path=find_dotenv())

# Optional OCR dependencies are imported lazily within extract_from_pdf
import re
from .common_utils import (
    normalize_price,
    detect_currency,
    detect_brand,
    gpt_clean_text,
    safe_json_parse,
)
import time
from . import ocr_llm_fallback
from pathlib import Path
from .debug_utils import save_debug, set_output_subdir
from .prompt_utils import prompts_for_pdf
from .github_upload import upload_folder, _sanitize_repo_path

MIN_CODE_RATIO = 0.70
MIN_ROWS_PARSER = 500
CODE_RE = re.compile(r"^([A-ZÇĞİÖŞÜ0-9][A-ZÇĞİÖŞÜ0-9\-/]{1,})", re.I)

logger = logging.getLogger("smart_price")


def _norm(s: Any) -> str:
    """Normalize ``s`` for fuzzy header matching."""
    return unicodedata.normalize("NFKD", str(s)).lower()


def header_match(
    cell: Any, candidates: Sequence[str], *, match_type: str | None = None
) -> bool:
    """Return True if ``cell`` fuzzily matches any of ``candidates``."""
    norm_candidates = [_norm(c) for c in candidates]
    if difflib.get_close_matches(_norm(cell), norm_candidates, cutoff=0.75):
        logger.info("header_match", extra={"header": cell, "match_type": match_type})
        return True
    return False


_patterns = [
    re.compile(
        r"^(.*?)\s{2,}([\d\.,]+)\s*(?:TL|TRY|EUR|USD|\$|€)?$",
        re.MULTILINE | re.IGNORECASE,
    ),
    re.compile(
        r"([A-Z0-9\-\s/]{5,50})\s+([\d\.,]+)\s*(?:TL|TRY|EUR|USD|\$|€)?", re.IGNORECASE
    ),
    re.compile(r"Item Code:\s*(.*?)\s*Price:\s*([\d\.,]+)", re.IGNORECASE),
    re.compile(r"Ürün No:\s*(.*?)\s*Birim Fiyat:\s*([\d\.,]+)", re.IGNORECASE),
]


def _basename(fp: Any, filename: Optional[str] = None) -> str:
    """Return best-effort basename for a file path or buffer."""
    if filename:
        return os.path.basename(filename)
    if isinstance(fp, (str, bytes, os.PathLike)):
        return os.path.basename(fp)
    name = getattr(fp, "name", None)
    if isinstance(name, str):
        return os.path.basename(name)
    return ""


def extract_from_pdf(
    filepath: str | IO[bytes],
    *,
    filename: str | None = None,
    log: Optional[Callable[[str, str], None]] = None,
    prompt: str | dict[int, str] | None = None,
) -> pd.DataFrame:
    """Extract product information from a PDF file."""
    page_summary: list[dict[str, object]] = []

    def notify(message: str, level: str = "info") -> None:
        logger.info(message)
        if log:
            try:
                log(message, level)
            except Exception as exc:  # pragma: no cover - log callback errors
                logger.error("log callback failed: %s", exc)

    src = _basename(filepath, filename)
    output_stem = Path(src).stem
    sanitized_base = _sanitize_repo_path(output_stem)
    set_output_subdir(output_stem)
    guide_prompt = prompt or prompts_for_pdf(src)
    notify(f"Processing {src} started at {datetime.now():%Y-%m-%d %H:%M:%S}")
    total_start = time.time()

    def _llm_extract_from_image(text: str) -> list[dict]:
        """Use a language model to extract product names and prices from OCR text."""
        # pragma: no cover - not exercised in tests
        notify("LLM fazı başladı")
        # Environment already loaded at module import time
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or not text:
            notify("LLM returned no data")
            return []

        try:
            from openai import OpenAI
        except Exception as exc:  # pragma: no cover - optional dep missing
            notify(f"openai import failed: {exc}")
            notify("LLM returned no data")
            return []

        client = OpenAI(api_key=api_key)

        model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
        excerpt = text[:200].replace("\n", " ")
        logger.debug("Using model %s on text excerpt: %r", model_name, excerpt)

        prompt = """
Sen bir PDF fiyat listesi analiz asistanısın. Amacın, PDF’lerdeki ürün tablosu/ürün satırlarını ve bunların üst başlıklarını tam olarak, eksiksiz ve yapısal şekilde çıkarmaktır.

**Çalışma Akışın:**

1. **Her PDF için, özel extraction talimatları olup olmadığını kontrol etmelisin:**
    - Sistemde “extraction_guide” adında bir referans dosyası olabilir.
    - Eğer bu dosya mevcutsa ve işlediğin PDF’ye (veya sayfa/alanına) ait özel bir extraction promptu/talimatı varsa, önce bu talimata uygun şekilde çıkarım yap.
    - Eğer dosyada talimat bulunamazsa veya extraction_guide dosyası hiç yoksa, aşağıdaki _Genel Extraction Talimatları_ ile devam et.

2. **Dosya veya talimat yoksa, hata verme; genel kurallarla standart extraction yap.**

---

### **Genel Extraction Talimatları:**

- Her ürün satırının;
    - Hangi ana başlık altında olduğunu (“Ana_Baslik”)
    - Hangi alt başlık altında olduğunu (“Alt_Baslik” – varsa)
    - Ürün kodu, fiyatı, açıklaması/özellikleri, varsa adet, birim, para birimi, kutu adedi, marka gibi tüm alanlarını
    - PDF dosya adı (“Kaynak_Dosya”) ve sayfa numarasını (“Sayfa”)
    açık şekilde ayrıştır.

- Tablo başlıklarını, alt başlıkları, genel açıklamaları **veri satırı olarak alma**;
  sadece gerçek ürün satırlarını çıkart.

- Çıktı formatın JSON dizi olacak.
  Her veri satırı için:
    - Ana_Baslik (zorunlu)
    - Alt_Baslik (varsa, zorunlu değil)
    - Malzeme_Kodu (zorunlu)
    - Açıklama/Özellikler (varsa)
    - Fiyat (zorunlu)
    - Para_Birimi (yoksa “TL” yaz)
    - Kaynak_Dosya
    - Sayfa
    - (Varsa ek alanlar: Adet, Birim, Marka, Kutu_Adedi...)

---

### **Extraction_guide Kullanımı:**
- extraction_guide adlı dosya varsa, PDF başlığına veya dosya adına uygun talimatı uygula.
- Bulamazsan veya extraction_guide yoksa, bu prompttaki _Genel Extraction Talimatları_ ile çalış.

---

### **Çıktı Örneği:**

```
[
  {
    "Ana_Baslik": "IE3 ALÜMİNYUM GÖVDELİ IEC 3~FAZLI ASENKRON ELEKTRİK MOTORLARI",
    "Alt_Baslik": "2k-3000 d/dak",
    "Malzeme_Kodu": "3MAS 80MA2",
    "Açıklama": "0.55 KW",
    "Fiyat": "110,00",
    "Para_Birimi": "USD",
    "Kaynak_Dosya": "Omega Motor Fiyat Listesi 2025.pdf",
    "Sayfa": "14"
  }
]
```
        """

        save_debug("llm_prompt", 1, prompt)

        logger.debug("LLM prompt length: %d", len(prompt))
        logger.debug("LLM prompt excerpt: %r", prompt[:200])

        try:
            start_llm = time.time()
            resp = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            logger.info("OpenAI request took %.2fs", time.time() - start_llm)
            time.sleep(0.5)
            content = resp.choices[0].message.content
            save_debug("llm_response", 1, content)
            logger.debug("LLM raw response: %r", content.strip()[:200])
            try:
                cleaned = gpt_clean_text(content)
                items = safe_json_parse(cleaned)
                if items is None:
                    raise ValueError("parse failed")
                logger.debug("First parsed items: %r", items[:2])
                if not items:
                    excerpt = text[:100].replace("\n", " ")
                    notify(
                        f"no items parsed by {model_name}; OCR text excerpt: {excerpt!r}"
                    )
                    return []
            except Exception:
                notify(f"LLM returned invalid JSON: {content!r}")
                notify("LLM returned no data")
                return []
        except Exception as exc:
            notify(f"openai request failed: {exc}")
            notify("LLM returned no data")
            return []

        results = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("product") or "").strip()
            price_raw = str(item.get("price", "")).strip()
            val = normalize_price(price_raw)
            if name and val is not None:
                results.append(
                    {
                        "Malzeme_Adi": name,
                        "Fiyat": val,
                        "Para_Birimi": detect_currency(price_raw),
                    }
                )
        count = len(results)
        if count:
            notify(f"LLM parsed {count} items")
        else:
            notify("LLM returned no data")
        return results

    tmp_for_llm: str | None = None

    def cleanup() -> None:
        if tmp_for_llm:
            try:
                os.remove(tmp_for_llm)
            except Exception as exc:
                notify(f"temp file cleanup failed: {exc}")

    try:
        if isinstance(filepath, (str, bytes, os.PathLike)):
            path_for_llm = filepath
        else:
            try:
                filepath.seek(0)
            except Exception as exc:
                notify(f"seek failed: {exc}")
            pdf_bytes = filepath.read()
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            tmp.write(pdf_bytes)
            tmp.close()
            tmp_for_llm = tmp.name
            path_for_llm = tmp_for_llm

        notify("G\u00f6rseller olu\u015fturuluyor...")
        result = ocr_llm_fallback.parse(
            path_for_llm,
            output_name=output_stem if tmp_for_llm else None,
            prompt=guide_prompt,
        )
        notify("Sat\u0131rlar\u0131n g\u00f6rselleri haz\u0131rlan\u0131yor...")
        page_summary = getattr(result, "page_summary", [])
    except Exception as exc:
        notify(f"PDF error for {filepath}: {exc}")
        logger.exception("PDF error for %s", filepath)
        duration = time.time() - total_start
        notify(f"Failed {src} after {duration:.2f}s")
        cleanup()
        return pd.DataFrame()

    if result.empty:
        cleanup()
        duration = time.time() - total_start
        notify(f"Finished {src} via LLM with 0 rows in {duration:.2f}s")
        debug_dir = (
            Path(os.getenv("SMART_PRICE_DEBUG_DIR", "LLM_Output_db")) / output_stem
        )
        set_output_subdir(None)
        upload_folder(debug_dir, remote_prefix=f"LLM_Output_db/{debug_dir.name}")
        return result

    result["Para_Birimi"] = result["Para_Birimi"].fillna("TL")
    result["Kaynak_Dosya"] = _basename(filepath, filename)
    result["Yil"] = None
    brand_from_file = detect_brand(_basename(filepath, filename))
    if brand_from_file:
        result["Marka"] = brand_from_file
    else:
        result["Marka"] = result["Descriptions"].apply(detect_brand)
    result["Kategori"] = None
    if "Kisa_Kod" not in result.columns:
        result["Kisa_Kod"] = None
    if "Ana_Baslik" not in result.columns:
        result["Ana_Baslik"] = None
    if "Alt_Baslik" not in result.columns:
        result["Alt_Baslik"] = None
    base_name_no_ext = Path(_basename(filepath, filename)).stem
    result["Record_Code"] = (
        sanitized_base
        + "|"
        + result["Sayfa"].astype(str)
        + "|"
        + (result.groupby("Sayfa").cumcount() + 1).astype(str)
    )
    result["Image_Path"] = result["Sayfa"].apply(
        lambda page_num: f"LLM_Output_db/{sanitized_base}/page_image_page_{int(page_num):02d}.png"
    )
    cols = [
        "Malzeme_Kodu",
        "Descriptions",
        "Kisa_Kod",
        "Fiyat",
        "Para_Birimi",
        "Marka",
        "Kaynak_Dosya",
        "Sayfa",
        "Record_Code",
        "Ana_Baslik",
        "Alt_Baslik",
        "Image_Path",
    ]
    result_df = result[cols].copy()
    duration = time.time() - total_start
    notify(f"Finished {src} via LLM with {len(result_df)} rows in {duration:.2f}s")
    if hasattr(result_df, "__dict__"):
        object.__setattr__(result_df, "page_summary", page_summary)
    cleanup()
    debug_dir = Path(os.getenv("SMART_PRICE_DEBUG_DIR", "LLM_Output_db")) / output_stem
    set_output_subdir(None)
    upload_folder(debug_dir, remote_prefix=f"LLM_Output_db/{debug_dir.name}")
    return result_df
