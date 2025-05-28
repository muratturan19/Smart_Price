import argparse
import csv
import os
import sqlite3
import logging
import pandas as pd
import pytesseract

from smart_price.core.extract_excel import extract_from_excel
from smart_price.core.extract_pdf import extract_from_pdf
from smart_price.core.logger import init_logging

logger = logging.getLogger("smart_price")

def _configure_tesseract() -> None:
    """Configure pytesseract paths and log available languages."""
    os.environ["TESSDATA_PREFIX"] = r"D:\\Program Files\\Tesseract-OCR"
    pytesseract.pytesseract.tesseract_cmd = (
        r"D:\\Program Files\\Tesseract-OCR\\tesseract.exe"
    )
    try:
        langs = (
            pytesseract.get_languages(config="")
            if hasattr(pytesseract, "get_languages")
            else []
        )
        logger.info("Available Tesseract languages: %s", langs)
        if "tur" not in langs:
            logger.error(
                "Tesseract language model 'tur' not found. "
                "Please install or copy the model into the tessdata folder."
            )
    except Exception as exc:  # pragma: no cover - unexpected errors
        logger.error("Tesseract language query failed: %s", exc)



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract prices from Excel and PDF files")
    parser.add_argument('files', nargs='+', help='Input Excel or PDF files')
    parser.add_argument('-o', '--output', default=os.path.join('output', 'merged_prices.xlsx'), help='Output Excel file path')
    parser.add_argument('--db', default=os.path.join('output', 'fiyat_listesi.db'), help='Output SQLite DB path')
    parser.add_argument('--log', default=os.path.join('output', 'source_log.csv'), help='CSV log path')
    return parser.parse_args()


def main() -> None:
    init_logging()
    _configure_tesseract()
    args = parse_args()
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    os.makedirs(os.path.dirname(args.db), exist_ok=True)
    os.makedirs(os.path.dirname(args.log), exist_ok=True)
    all_extracted = []
    log_rows = []
    for path in args.files:
        name = os.path.basename(path)
        ext = os.path.splitext(name)[1].lower()
        try:
            if ext in ('.xlsx', '.xls'):
                df = extract_from_excel(path)
            elif ext == '.pdf':
                df = extract_from_pdf(path)
            else:
                logger.info("Skipping unsupported file: %s", name)
                continue
            row_count = len(df)
            if row_count:
                logger.info("%s: %d records", name, row_count)
                all_extracted.append(df)
            else:
                logger.info("%s: no data found", name)
            log_rows.append({'file': name, 'format': ext.lstrip('.'), 'rows': row_count, 'error': ''})
        except Exception as exc:  # pragma: no cover - unexpected errors
            logger.error("Error processing %s: %s", name, exc)
            log_rows.append({'file': name, 'format': ext.lstrip('.'), 'rows': 0, 'error': str(exc)})
    if not all_extracted:
        logger.info("No data extracted from given files.")
        return
    master = pd.concat(all_extracted, ignore_index=True)
    master.drop_duplicates(subset=["Malzeme_Kodu", "Descriptions"], keep="last", inplace=True)
    master.sort_values(by="Descriptions", inplace=True)
    master.to_excel(args.output, index=False)
    logger.info("Saved %d records to %s", len(master), args.output)

    conn = sqlite3.connect(args.db)
    with conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS prices (
            material_code TEXT,
            description TEXT,
            price REAL,
            price_currency TEXT,
            source_file TEXT,
            source_page INTEGER,
            year INTEGER,
            brand TEXT,
            category TEXT
            )"""
        )
        master.rename(
            columns={
                "Malzeme_Kodu": "material_code",
                "Descriptions": "description",
                "Fiyat": "price",
                "Para_Birimi": "price_currency",
                "Kaynak_Dosya": "source_file",
                "Sayfa": "source_page",
                "Yil": "year",
                "Marka": "brand",
                "Kategori": "category",
            },
            inplace=True,
        )
        master.to_sql("prices", conn, if_exists="replace", index=False)
    conn.close()
    logger.info("Database written to %s", args.db)

    with open(args.log, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['file', 'format', 'rows', 'error'])
        writer.writeheader()
        writer.writerows(log_rows)
    logger.info("Source log written to %s", args.log)


if __name__ == '__main__':
    main()
