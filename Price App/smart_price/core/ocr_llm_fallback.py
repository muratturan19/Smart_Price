from __future__ import annotations

import base64
import io
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable, Sequence, TYPE_CHECKING, Callable
import asyncio
import inspect

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

import pandas as pd

import tempfile
from pathlib import Path


from .common_utils import (
    gpt_clean_text,
    normalize_price,
    detect_currency,
    normalize_currency,
    safe_json_parse,
    log_metric,
)
from smart_price.utils.prompt_builder import get_prompt_for_file
from .prompt_utils import RAW_HEADER_HINT
from .debug_utils import save_debug, save_debug_image, set_output_subdir
from .token_utils import (
    num_tokens_from_messages,
    num_tokens_from_text,
    log_token_counts,
)
from .github_upload import upload_folder
from smart_price import config

if TYPE_CHECKING:  # pragma: no cover - type hints only
    from PIL import Image  # noqa: F401

logger = logging.getLogger("smart_price")

DEBUG = os.getenv("SMART_PRICE_DEBUG", "1") == "1"


def _get_openai_timeout() -> float:
    """Return ``OpenAI`` request timeout in seconds."""
    try:
        return float(os.getenv("OPENAI_REQUEST_TIMEOUT", "120"))
    except Exception:
        return 120.0

DEFAULT_PROMPT = """
Sen bir PDF fiyat listesi analiz asistanısın. Amacın, PDF’lerdeki ürün tablosu/ürün satırlarını ve bunların üst başlıklarını tam olarak, eksiksiz ve yapısal şekilde çıkarmaktır.

**Çalışma Akışın:**

1. Bu PDF için extraction_guide içinde tanımlı bir talimat varsa önce bu talimata uygun şekilde çıkarım yap. Talimat yoksa aşağıdaki _Genel Extraction Talimatları_ ile devam et.
2. Talimat bulunamazsa hata verme; genel kurallarla standart extraction yap.

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

Çıktıdaki kolon adları tam olarak: Malzeme_Kodu, Açıklama, Fiyat, Para_Birimi, Ana_Baslik, Alt_Baslik, Sayfa. İlk satıra başlık yazmayın.

---

### **Extraction_guide Kullanımı:**
- extraction_guide dosyasında bu PDF'e özel bir talimat tanımlıysa otomatik olarak uygulanır.
- Talimat yoksa bu prompttaki _Genel Extraction Talimatları_ geçerlidir.

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


def _range_bounds(pages: Sequence[int] | range | None) -> tuple[int | None, int | None]:
    """Return first and last page numbers from ``pages``."""
    if not pages:
        return None, None
    try:
        start = pages.start  # type: ignore[attr-defined]
        end = pages.stop - 1  # type: ignore[attr-defined]
    except AttributeError:
        seq = list(pages)  # type: ignore[arg-type]
        if not seq:
            return None, None
        start, end = min(seq), max(seq)
    return start, end


def split_image_horizontally(image: "Image") -> list["Image"]:
    """Return top and bottom halves of ``image``.

    Parameters
    ----------
    image : PIL Image
        Image to split horizontally.

    Returns
    -------
    list of Image
        ``[top, bottom]`` halves of the original image.
    """
    crop = getattr(image, "crop", None)
    size = getattr(image, "size", None)
    if callable(crop) and size:
        width, height = size
        mid = int(height / 2)
        top = crop((0, 0, width, mid))
        bottom = crop((0, mid, width, height))
        logger.info("image split horizontally width=%s height=%s", width, height)
        return [top, bottom]
    return [image]




def parse(
    pdf_path: str,
    page_range: Iterable[int] | range | None = None,
    *,
    output_name: str | None = None,
    prompt: str | dict[int, str] | None = None,
    dpi: int | None = None,
    progress_callback: Callable[[float], None] | None = None,
) -> pd.DataFrame:
    """Parse ``pdf_path`` using a minimal Vision+LLM pipeline."""

    logger.info("==> BEGIN parse %s", pdf_path)
    if output_name is None:
        output_name = Path(pdf_path).stem

    set_output_subdir(output_name)

    if prompt is None:
        prompt = get_prompt_for_file(Path(pdf_path).name)

    try:
        from pdf2image import convert_from_path  # type: ignore
    except Exception as exc:
        logger.error("pdf2image unavailable: %s", exc)
        return pd.DataFrame()

    dpi_val = int(dpi) if dpi is not None else 150
    kwargs: dict[str, int] = {"dpi": dpi_val}
    first, last = _range_bounds(page_range)
    if first is not None:
        kwargs["first_page"] = first
    if last is not None:
        kwargs["last_page"] = last
    images = convert_from_path(pdf_path, poppler_path=str(config.POPPLER_PATH), **kwargs)
    logger.info("pdf2image pages=%s", len(images))
    page_start = first if first is not None else 1
    total_pages = len(images)

    try:
        import openai as _openai
    except Exception as exc:
        logger.error("OpenAI import failed: %s", exc)
        return pd.DataFrame()

    client_cls = getattr(_openai, "OpenAI", None) or getattr(_openai, "AsyncOpenAI", None)
    if client_cls is None:
        logger.error("OpenAI client not available")
        return pd.DataFrame()

    try:
        openai_max_retries = int(os.getenv("OPENAI_MAX_RETRIES", "0"))
    except Exception:
        openai_max_retries = 0
    try:
        _openai.api_requestor._DEFAULT_NUM_RETRIES = openai_max_retries
    except Exception:
        pass

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY environment variable not set")
        raise ValueError("OPENAI_API_KEY not set")

    client = client_cls(
        api_key=api_key,
        timeout=_get_openai_timeout(),
    )
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o")

    def _get_prompt(page: int) -> str:
        fallback = RAW_HEADER_HINT + "\n" + DEFAULT_PROMPT
        if isinstance(prompt, dict):
            return prompt.get(page, prompt.get(0, fallback))
        return prompt if prompt is not None else fallback

    def process_page(args: tuple[int, "Image.Image"]):
        idx, img = args
        page_num = page_start + idx - 1

        def _send(image: "Image.Image") -> list[dict]:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            try:
                image.save(tmp.name, format="JPEG")
                data = base64.b64encode(Path(tmp.name).read_bytes()).decode()
            finally:
                try:
                    tmp.close()
                    os.unlink(tmp.name)
                except Exception:
                    pass
            prompt_text = _get_prompt(page_num)
            logger.info("LLM request start page %d", page_num)
            resp = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_text},
                            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + data}},
                        ],
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0,
            )
            if inspect.iscoroutine(resp):
                resp = asyncio.run(resp)
            content = resp.choices[0].message.content or "[]"
            items = safe_json_parse(gpt_clean_text(content))
            if isinstance(items, dict) and "products" in items:
                items = items.get("products")
            if not isinstance(items, list):
                items = [] if items is None else [items]
            for it in items:
                if isinstance(it, dict):
                    it.setdefault("Sayfa", page_num)
            return items

        error_types = (TimeoutError,)
        openai_error = getattr(_openai, "error", None)
        if openai_error is not None:
            error_types = error_types + (
                getattr(_openai, "APITimeoutError", TimeoutError),
                getattr(openai_error, "Timeout", TimeoutError),
                getattr(openai_error, "APIConnectionError", TimeoutError),
            )

        try:
            rows = _send(img)
            status = "success" if rows else "empty"
            summary = {"page_number": page_num, "rows": len(rows), "status": status}
            return idx, rows, summary
        except error_types as exc:
            logger.error("LLM request failed on page %d: %s", page_num, exc)
            parts = split_image_horizontally(img)
            if len(parts) > 1:
                all_rows: list[dict] = []
                page_summaries: list[dict[str, object]] = []
                for _part in parts:
                    try:
                        r = _send(_part)
                        state = "success" if r else "empty"
                        page_summaries.append({"page_number": page_num, "rows": len(r), "status": state, "note": "timeout split"})
                        all_rows.extend(r)
                    except Exception as exc2:
                        logger.error("LLM request failed on page %d: %s", page_num, exc2)
                        page_summaries.append({"page_number": page_num, "rows": 0, "status": "error", "note": "timeout split"})
                return idx, all_rows, page_summaries
            max_retries = getattr(config, "MAX_RETRIES", 0)
            attempts = 0
            while attempts < max_retries:
                attempts += 1
                try:
                    rows = _send(img)
                    note = "timeout retry"
                    summary = {"page_number": page_num, "rows": len(rows), "status": "success", "note": note}
                    return idx, rows, summary
                except error_types as exc2:
                    logger.error("LLM request failed on page %d: %s", page_num, exc2)
            return idx, [], {"page_number": page_num, "rows": 0, "status": "error", "note": "gave up"}
        except Exception as exc:
            logger.error("LLM request failed on page %d: %s", page_num, exc)
            return idx, [], {"page_number": page_num, "rows": 0, "status": "error", "note": str(exc)}

    try:
        env_workers = int(os.getenv("SMART_PRICE_LLM_WORKERS", "0"))
    except Exception:
        env_workers = 0
    if env_workers:
        workers = env_workers
    else:
        workers = min(5, len(images)) or 1
    rows: list[dict[str, object]] = []
    page_summary: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(process_page, (i, img)) for i, img in enumerate(images, start=1)]
        for fut in futures:
            idx, page_rows, summary = fut.result()
            rows.extend(page_rows)
            if isinstance(summary, list):
                page_summary.extend(summary)
            else:
                page_summary.append(summary)
            if progress_callback and total_pages:
                try:
                    progress_callback(idx / total_pages)
                except Exception:
                    pass

    df = pd.DataFrame(rows)
    if hasattr(df, "__dict__"):
        object.__setattr__(df, "page_summary", page_summary)

    set_output_subdir(None)
    logger.info("==> END parse %s", pdf_path)
    return df
