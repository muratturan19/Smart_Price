import argparse
import os
import pandas as pd

from core.extract_excel import extract_from_excel
from core.extract_pdf import extract_from_pdf


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract prices from Excel and PDF files")
    parser.add_argument('files', nargs='+', help='Input Excel or PDF files')
    parser.add_argument('-o', '--output', default='merged_prices.xlsx', help='Output Excel file path')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    all_extracted = []
    for path in args.files:
        name = os.path.basename(path)
        if name.lower().endswith(('.xlsx', '.xls')):
            df = extract_from_excel(path)
        elif name.lower().endswith('.pdf'):
            df = extract_from_pdf(path)
        else:
            print(f"Skipping unsupported file: {name}")
            continue
        if not df.empty:
            print(f"{name}: {len(df)} records")
            all_extracted.append(df)
        else:
            print(f"{name}: no data found")
    if not all_extracted:
        print("No data extracted from given files.")
        return
    master = pd.concat(all_extracted, ignore_index=True)
    # Basic cleanup using the new column names
    required_cols = ['description', 'price']
    missing = [col for col in required_cols if col not in master.columns]
    if missing:
        raise ValueError(f"Missing expected columns: {', '.join(missing)}")

    master.dropna(subset=['description', 'price'], inplace=True)
    master['description'] = (
        master['description']
        .astype(str)
        .str.strip()
        .str.upper()
    )
    master = master[master['description'] != '']

    master['price'] = pd.to_numeric(master['price'], errors='coerce')
    master.dropna(subset=['price'], inplace=True)
    master = master[master['price'] > 0.01]

    if 'material_code' in master.columns:
        dedup_cols = ['material_code', 'description']
    else:
        dedup_cols = ['description']
    master.drop_duplicates(subset=dedup_cols, keep='last', inplace=True)

    master.sort_values(by='description', inplace=True)
    master.to_excel(args.output, index=False)
    print(f"Saved {len(master)} records to {args.output}")


if __name__ == '__main__':
    main()
