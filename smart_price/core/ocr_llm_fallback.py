from __future__ import annotations

import base64
import logging
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable, Sequence, TYPE_CHECKING
from dotenv import load_dotenv

try:
    load_dotenv("../..")
except TypeError:  # pragma: no cover - allow stub without args
    load_dotenv()

import pandas as pd

import tempfile
from pathlib import Path


from .common_utils import (
    gpt_clean_text,
    normalize_price,
    detect_currency,
    safe_json_parse,
)
from .debug_utils import save_debug, save_debug_image, set_output_subdir

if TYPE_CHECKING:  # pragma: no cover - type hints only
    from PIL import Image  # noqa: F401

logger = logging.getLogger("smart_price")


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
    """

    if output_name is None:
        output_name = Path(pdf_path).stem

    set_output_subdir(output_name)
    total_start = time.time()

    try:
        from pdf2image import convert_from_path  # type: ignore
    except Exception as exc:  # pragma: no cover - optional deps missing
        logger.error("pdf2image unavailable: %s", exc)
        return pd.DataFrame()

    try:
        kwargs = {"dpi": 300}
        first, last = _range_bounds(page_range)
        if first is not None:
            kwargs["first_page"] = first
        if last is not None:
            kwargs["last_page"] = last
        start_convert = time.time()
        images = convert_from_path(pdf_path, **kwargs)
        logger.info(
            "pdf2image.convert_from_path took %.2fs for %d pages",
            time.time() - start_convert,
            len(images),
        )
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

    prompt = """
    Sen bir Malzeme_Kodu - Fiyat çıkarma asistanısın ve görevin karmaşık yapılı,
    farklı ifadelerler yazılmış pdf dosyalarından Malzeme_Kodu - Fiyat ve varsa
    diğer bilgileri çıkarmak. PDF dosyası sana sayfa sayfa image olarak
    verilecek. Birçok pdf çıktısı tek dosyada toplanacağından çıkarımlar aynı
    başlıklarla yapılmalı.

    Aşağıda detaylı çalışma talimatların var:

    1. Başlık Kümeleri (RAW_HEADERS)
    Malzeme_Kodu (RAW_CODE_HEADERS):
    Ürün, ürün adı, ürün kodu, kod, malzeme, malzeme kodu, part no, part code,
    item code, code, stock code, vs.

    Açıklama (RAW_DESC_HEADERS):
    Açıklama, tip, tanım, description

    Fiyat (RAW_PRICE_HEADERS):
    Fiyat, birim fiyat, price, tl, amount, tutar, unit price, vs.

    Ek Sütunlar:
    Adet, quantity, birim, para birimi, marka, kutu adedi...

    2. Extraction Kuralları
    Tabloda RAW_CODE_HEADERS ile eşleşen başlık altındaki tüm satırları veri
    olarak işle.

    Her satırda Malzeme_Kodu ve Fiyat zorunlu; diğer alanlar varsa al, yoksa boş
    bırak.

    Ek bilgiler (Açıklama, Adet, Para Birimi vs.) mevcutsa çek, yoksa hata olarak
    sayma.

    Para birimi görünmüyorsa, varsayılan TL olarak ekle.

    3. Extraction Sırasında
    Tablo başlığı, alt başlıklar veya sayfa açıklamaları kesinlikle veri olarak
    alınmayacak.

    Sadece RAW_HEADERS ile eşleşen sütunların altındaki gerçek ürün satırları
    çıkarılacak.

    Malzeme_Kodu veya Fiyat boş olan satır atılacak.
    
    4. Eğer bir ürün kodunun bulunduğu satırda, sağında birden fazla fiyat sütunu varsa:
    Her fiyat sütununun başlığını ürün kodunun sonuna “-” ile ekleyip,
    ortaya çıkan bu yeni ifadeyi (ör. “DK24 - Plastik”) Malzeme_Kodu olarak kaydet.
    Fiyatı ilgili değeriyle birlikte yaz.
    Diğer alanlar yoksa boş bırak, açıklama alanını kullanma.

    Örnek:

    Tablo:
    Ürün Kodu	Plastik	Yedek Tek Dişli	DK Takım
    DK24	45	80	205
    Doğru Extraction Çıktısı:

    [
      {
        "Malzeme_Kodu": "DK24 - Plastik",
        "Fiyat": "45",
        "Para_Birimi": "TL"
      },
      {
        "Malzeme_Kodu": "DK24 - Yedek Tek Dişli",
        "Fiyat": "80",
        "Para_Birimi": "TL"
      },
      {
        "Malzeme_Kodu": "DK24 - DK Takım",
        "Fiyat": "205",
        "Para_Birimi": "TL"
      }
    ]


    5. Çıktı Formatı
    Her veri satırı (varsa):

    Malzeme_Kodu
    Açıklama
    Fiyat
    Adet
    Birim
    Para_Birimi
    Marka
    Kutu_Adedi
    ... (tabloya göre diğer ek alanlar)

    Çıktı: JSON listesi

    6. Dinamik ve Dili Bağımsız
    Başlıklar Türkçe, İngilizce, farklı varyasyonlarla gelebilir.

    Senin görevin başlığı tanımak ve doğru alanlara atamak.

    7. Yanlışlar ve Yasaklar
    Tablo başlığı, sayfa açıklamaları, dipnotlar ürün verisi olarak alınmayacak.

    Sadece ürün satırları dönecek.

    Bir satırda birden fazla ürün varsa, her biri için ayrı satır üretilecek.

    8. Örnek
    [
      {
        "Malzeme_Kodu": "JKS19",
        "Açıklama": "Jawtex Plastik",
        "Fiyat": "90,00",
        "Adet": "50",
        "Birim": "Adet",
        "Para_Birimi": "TL"
      }
    ]
    Ek örnek:
    Tabloda: Ürün Kodu: Ax2234, Description: Çap 12 O ring, Price: 12, Adet: 50
    Çıktı:
    Malzeme_Kodu: Ax2234, Açıklama: Çap 12 O ring, Fiyat: 12₺, Adet: 50

    Kısa Samimi Versiyonu:
    Belirttiğim başlıklar ve eşanlamlılar (RAW_HEADERS) ile eşleşen tablo
    sütunlarının altındaki tüm veri satırlarını, ilgili alanlarla birlikte
    eksiksiz döndür.
    Tablo başlıkları, alt başlıklar ve sayfa üzerindeki genel açıklamalar asla
    veri satırı olarak alınmasın.
    """

    rows: list[dict[str, object]] = []
    page_summary: list[dict[str, object]] = []

    lock = threading.Lock()
    running = 0

    def process_page(args: tuple[int, "Image.Image"]):
        nonlocal running
        idx, img = args
        start = time.time()
        with lock:
            running += 1
            current = running
        logger.info("LLM request start page %d (running=%d)", idx, current)

        page_rows: list[dict[str, object]] = []
        status = "success"
        note = None
        img_path = save_debug_image("page_image", idx, img)
        tmp_path = img_path
        created_tmp = False
        if tmp_path is None:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            img.save(tmp.name, format="PNG")
            tmp.close()
            tmp_path = Path(tmp.name)
            created_tmp = True
        try:
            with open(tmp_path, "rb") as f:
                image_bytes = f.read()
            img_base64 = base64.b64encode(image_bytes).decode()
            api_start = time.time()
            resp = openai.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": "data:image/png;base64," + img_base64},
                            },
                        ],
                    }
                ],
                temperature=0,
            )
            logger.info(
                "OpenAI request for page %d took %.2fs", idx, time.time() - api_start
            )
            content = resp.choices[0].message.content
            save_debug("llm_response", idx, content or "")
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
            code = item.get("Malzeme_Kodu") or item.get("Malzeme Kodu")
            descr = item.get("Açıklama")
            price_raw = str(item.get("Fiyat", "")).strip()
            kutu_adedi = item.get("Kutu_Adedi") or item.get("Kutu Adedi")
            para_birimi = item.get("Para_Birimi") or item.get("Para Birimi")
            if para_birimi is None:
                para_birimi = detect_currency(price_raw)
            page_rows.append(
                {
                    "Malzeme_Kodu": code,
                    "Descriptions": descr,
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
        logger.info(
            "LLM request end page %d (running=%d, %.2fs)", idx, current, dur
        )
        return idx, page_rows, summary

    workers = int(os.getenv("SMART_PRICE_LLM_WORKERS", "5"))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(process_page, (i, img)) for i, img in enumerate(images, start=1)]
        results = [f.result() for f in futures]

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
    logger.debug("[%s] DataFrame oluşturuldu: %d satır", pdf_path, len(df))
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
    total_dur = time.time() - total_start
    logger.info("Finished %s with %d rows in %.2fs", pdf_path, len(df), total_dur)
    set_output_subdir(None)
    return df

