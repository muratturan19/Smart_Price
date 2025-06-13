from __future__ import annotations

import base64
import logging
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, Future, wait, FIRST_COMPLETED
from typing import Iterable, Sequence, TYPE_CHECKING, Callable

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

MAX_RETRIES = int(os.getenv("SMART_PRICE_MAX_RETRIES", "1"))

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


def parse(
    pdf_path: str,
    page_range: Iterable[int] | range | None = None,
    *,
    output_name: str | None = None,
    prompt: str | dict[int, str] | None = None,
    dpi: int | None = None,
    progress_callback: Callable[[float], None] | None = None,
) -> pd.DataFrame:
    """Parse ``pdf_path`` using GPT-4o vision.

    Parameters
    ----------
    pdf_path : str
        Path to the PDF file to parse.
    page_range : iterable of int or range, optional
        Pages to include when converting the PDF to images.
    output_name : str, optional
        Name of the debug output directory under ``LLM_Output_db``.  Defaults
        to ``Path(pdf_path).stem``.
    dpi : int, optional
        Resolution used when converting PDF pages to images. Overrides the
        ``SMART_PRICE_PDF_DPI`` environment variable. Defaults to ``150``.
    progress_callback : callable, optional
        Callback receiving a float ``0-1`` progress value after each page.
    """

    if output_name is None:
        output_name = Path(pdf_path).stem

    set_output_subdir(output_name)
    total_start = time.time()
    total_input_tokens = 0
    total_output_tokens = 0
    total_pages = 0
    processed_pages = 0

    if prompt is None:
        prompt = get_prompt_for_file(Path(pdf_path).name)

    try:
        from pdf2image import convert_from_path  # type: ignore
    except Exception as exc:  # pragma: no cover - optional deps missing
        logger.error("pdf2image unavailable: %s", exc)
        return pd.DataFrame()

    try:
        dpi_val = dpi if dpi is not None else os.getenv("SMART_PRICE_PDF_DPI")
        try:
            dpi_val = int(dpi_val) if dpi_val is not None else 150
        except Exception:
            dpi_val = 150
        kwargs = {"dpi": dpi_val}
        first, last = _range_bounds(page_range)
        if first is not None:
            kwargs["first_page"] = first
        if last is not None:
            kwargs["last_page"] = last
        start_convert = time.time()
        images = convert_from_path(
            pdf_path, poppler_path=str(config.POPPLER_PATH), **kwargs
        )
        logger.info(
            "pdf2image.convert_from_path took %.2fs for %d pages",
            time.time() - start_convert,
            len(images),
        )
        total_pages = len(images)
        processed_pages = 0
    except Exception as exc:  # pragma: no cover - conversion errors
        logger.error("pdf2image failed for %s: %s", pdf_path, exc)
        return pd.DataFrame()

    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        os.environ.setdefault("OPENAI_API_KEY", api_key)

    try:
        import openai
    except Exception as exc:  # pragma: no cover - import errors
        logger.error("OpenAI import failed: %s", exc)
        return pd.DataFrame()

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o")

    def _get_prompt(page: int) -> str:
        fallback = RAW_HEADER_HINT + "\n" + DEFAULT_PROMPT
        if isinstance(prompt, dict):
            return prompt.get(page, prompt.get(0, fallback))
        return prompt if prompt is not None else fallback

    rows: list[dict[str, object]] = []
    page_summary: list[dict[str, object]] = []

    lock = threading.Lock()
    running = 0

    timeout_errors: tuple[type[Exception], ...] = (TimeoutError,)
    api_timeout = getattr(openai, "APITimeoutError", None)
    if isinstance(api_timeout, type) and issubclass(api_timeout, BaseException):
        timeout_errors += (api_timeout,)
    err_mod = getattr(openai, "error", None)
    if err_mod is not None:
        err_timeout = getattr(err_mod, "Timeout", None)
        if isinstance(err_timeout, type) and issubclass(err_timeout, BaseException):
            timeout_errors += (err_timeout,)

    def process_page(args: tuple[int, "Image.Image"]):
        nonlocal running, total_input_tokens, total_output_tokens
        idx, img = args
        start = time.time()
        with lock:
            running += 1
            current = running
        logger.info("LLM request start page %d (running=%d)", idx, current)

        page_rows: list[dict[str, object]] = []
        status = "success"
        note = None
        retry = False
        img_path = save_debug_image("page_image", idx, img)
        tmp_path = img_path
        created_tmp = False
        if tmp_path is None:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            img.save(
                tmp.name,
                format="JPEG",
                quality=80,
                optimize=True,
                progressive=True,
            )
            tmp.close()
            tmp_path = Path(tmp.name)
            created_tmp = True
        try:
            with open(tmp_path, "rb") as f:
                image_bytes = f.read()
            img_base64 = base64.b64encode(image_bytes).decode()
            prompt_text = _get_prompt(idx)
            save_debug("llm_prompt", idx, prompt_text)
            logger.debug(
                "Prompt being used for extraction (truncated): %s",
                prompt_text[:200],
            )
            total_input_tokens += num_tokens_from_messages(
                [{"role": "user", "content": prompt_text}], model_name
            )
            api_start = time.time()
            resp = openai.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_text},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": "data:image/jpeg;base64," + img_base64
                                },
                            },
                        ],
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0,
                timeout=120,
            )
            logger.info(
                "OpenAI request for page %d took %.2fs", idx, time.time() - api_start
            )
            content = resp.choices[0].message.content
            logger.debug(
                "LLM response for page %d (truncated): %s",
                idx,
                (content or "")[:200],
            )
            total_output_tokens += num_tokens_from_text(content or "", model_name)
            save_debug("llm_response", idx, content or "")
        except timeout_errors as exc:  # pragma: no cover - request errors
            logger.error("OpenAI request timed out on page %d: %s", idx, exc)
            status = "error"
            note = "timeout"
            content = None
            retry = True
        except Exception as exc:  # pragma: no cover - request errors
            logger.error("OpenAI request failed on page %d: %s", idx, exc)
            status = "error"
            note = str(exc)
            content = None
        finally:
            if created_tmp:
                try:
                    os.remove(tmp_path)
                except Exception as exc:  # pragma: no cover - cleanup errors
                    logger.debug("temp file cleanup failed: %s", exc)

        cleaned = gpt_clean_text(content) if content else "[]"
        items = safe_json_parse(cleaned)
        if items is None:
            logger.error("LLM JSON parse failed on page %d", idx)
            status = "error"
            note = "parse error"
            items = []

        items = items if isinstance(items, list) else [items]
        for item in items:
            if not isinstance(item, dict):
                continue
            code = item.get("Malzeme_Kodu") or item.get("Malzeme Kodu")
            descr = item.get("Açıklama")
            main_title = item.get("Ana_Baslik") or item.get("Ana Baslik")
            sub_title = item.get("Alt_Baslik") or item.get("Alt Baslik")
            price_raw = str(item.get("Fiyat", "")).strip()
            kutu_adedi = item.get("Kutu_Adedi") or item.get("Kutu Adedi")
            para_birimi = item.get("Para_Birimi") or item.get("Para Birimi")
            if para_birimi is None:
                para_birimi = detect_currency(price_raw)
            para_birimi = normalize_currency(para_birimi)
            page_rows.append(
                {
                    "Malzeme_Kodu": code,
                    "Açıklama": descr,
                    "Ana_Baslik": main_title,
                    "Alt_Baslik": sub_title,
                    "Fiyat": normalize_price(price_raw),
                    "Birim": item.get("Birim"),
                    "Kutu_Adedi": kutu_adedi,
                    "Para_Birimi": para_birimi,
                    "Sayfa": idx,
                }
            )

        added = len(page_rows)
        if status == "success" and added == 0:
            status = "empty"

        summary = {
            "page_number": idx,
            "rows": added,
            "status": status,
            "note": note,
        }
        dur = time.time() - start
        with lock:
            running -= 1
            current = running
        logger.info("LLM request end page %d (running=%d, %.2fs)", idx, current, dur)
        return idx, page_rows, summary, retry

    workers = int(os.getenv("SMART_PRICE_LLM_WORKERS", "5"))
    if len(images) <= 2:
        workers = 1
    tasks = [(i, img) for i, img in enumerate(images, start=1)]
    results = []
    retry_counts: dict[int, int] = {}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures: dict[Future, tuple[int, "Image.Image"]] = {}
        while tasks or futures:
            while tasks and len(futures) < workers:
                task = tasks.pop(0)
                futures[ex.submit(process_page, task)] = task
            done, _ = wait(futures.keys(), return_when=FIRST_COMPLETED)
            for fut in done:
                task = futures.pop(fut)
                idx, rows_out, summary, retry = fut.result()
                if retry:
                    count = retry_counts.get(idx, 0)
                    if count < MAX_RETRIES:
                        retry_counts[idx] = count + 1
                        tasks.append(task)
                        continue
                    summary["status"] = "error"
                    summary["note"] = "gave up"
                    rows_out = []
                else:
                    if retry_counts.get(idx):
                        summary["note"] = "timeout retry"
                results.append((idx, rows_out, summary))
                processed_pages += 1
                if progress_callback and total_pages:
                    try:
                        progress_callback(processed_pages / total_pages)
                    except Exception:
                        pass

    results.sort(key=lambda r: r[0])
    for _idx, rows_out, summary in results:
        rows.extend(rows_out)
        page_summary.append(summary)

    logger.debug(
        "[%s] LLM Vision output: %d rows extracted from PDF",
        pdf_path,
        len(rows),
    )

    df = pd.DataFrame(rows)
    try:
        row_count = len(df)
    except Exception:
        row_count = len(rows)
    logger.debug("[%s] DataFrame oluşturuldu: %d satır", pdf_path, row_count)
    if hasattr(df, "columns"):
        if "Para_Birimi" not in df.columns:
            df["Para_Birimi"] = None
        df["Para_Birimi"] = df["Para_Birimi"].apply(normalize_currency)
        df["Para_Birimi"] = df["Para_Birimi"].fillna("₺")
    if hasattr(df, "columns"):
        if "Ana_Baslik" not in df.columns:
            df["Ana_Baslik"] = None
        if "Alt_Baslik" not in df.columns:
            df["Alt_Baslik"] = None
    if hasattr(df, "columns") and "Kutu_Adedi" in getattr(df, "columns", []):
        try:
            df["Kutu_Adedi"] = df["Kutu_Adedi"].astype("string")
        except Exception:  # pragma: no cover - DataFrame stub
            pass
    if hasattr(df, "empty") and not df.empty:
        base = Path(pdf_path).stem
        df["Record_Code"] = (
            base
            + "|"
            + df["Sayfa"].astype(str)
            + "|"
            + (df.groupby("Sayfa").cumcount() + 1).astype(str)
        )
    if hasattr(df, "__dict__"):
        object.__setattr__(df, "page_summary", page_summary)
        object.__setattr__(
            df,
            "token_counts",
            {
                "input": total_input_tokens,
                "output": total_output_tokens,
            },
        )
    total_dur = time.time() - total_start
    logger.info("Finished %s with %d rows in %.2fs", pdf_path, len(df), total_dur)
    log_metric("parse_pdf", len(page_summary), total_dur)
    log_token_counts(pdf_path, total_input_tokens, total_output_tokens)
    debug_dir = Path(os.getenv("SMART_PRICE_DEBUG_DIR", "LLM_Output_db")) / output_name
    text_dir = Path(os.getenv("SMART_PRICE_TEXT_DIR", "LLM_Text_db")) / output_name
    debug_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)
    set_output_subdir(None)
    logger.info("Debug klasörü GitHub'a yükleniyor...")
    ok = upload_folder(
        debug_dir,
        remote_prefix=f"LLM_Output_db/{debug_dir.name}",
        file_extensions=[".jpg"],
    )
    if ok:
        logger.info("Debug klasörü yüklendi")
    else:
        logger.warning("GitHub upload başarısız")
    if progress_callback and total_pages:
        try:
            progress_callback(1.0)
        except Exception:
            pass
    return df
