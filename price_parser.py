import pandas as pd
import pdfplumber
import os
import re
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox

# --- Konfigürasyon ve Yardımcı Fonksiyonlar ---

# Malzeme adı/kodu için arayabileceğimiz yaygın sütun başlıkları (Excel için)
POSSIBLE_PRODUCT_NAME_HEADERS = [
    'ürün adı', 'malzeme adı', 'ürün kodu', 'malzeme kodu', 'kod',
    'product name', 'product code', 'material code', 'item name', 'description'
]
# Malzeme kodu için kullanabileceğimiz başlıklar
POSSIBLE_CODE_HEADERS = [
    'malzeme kodu', 'ürün kodu', 'kod', 'product code', 'material code',
    'item code', 'code'
]
# Açıklama için kullanılabilecek başlıklar
POSSIBLE_DESCRIPTION_HEADERS = [
    'malzeme adı', 'ürün adı', 'açıklama', 'description', 'product name',
    'item name'
]
# Para birimi için
POSSIBLE_CURRENCY_HEADERS = ['para birimi', 'currency']
# Fiyat için arayabileceğimiz yaygın sütun başlıkları (Excel için)
POSSIBLE_PRICE_HEADERS = [
    'fiyat', 'birim fiyat', 'liste fiyatı', 'price', 'unit price', 'list price', 'tutar'
]

def clean_price(price_str):
    """Convert a raw price string to a ``float`` value.

    Parameters
    ----------
    price_str : str or Any
        String representation of the price. Currency symbols and thousand
        separators are allowed.

    Returns
    -------
    float or None
        Parsed price as a ``float`` if successful, otherwise ``None``.
    """
    if price_str is None:
        return None
    price_str = str(price_str).strip()
    # Para birimi sembollerini ve binlik ayraçlarını kaldır
    price_str = re.sub(r'[^\d,\.]', '', price_str) 
    # Türkçe virgül (ondalık) ve nokta (binlik) -> İngilizce nokta (ondalık)
    if ',' in price_str and '.' in price_str:
        if price_str.rfind('.') < price_str.rfind(','): # 1.234,56 formatı
            price_str = price_str.replace('.', '').replace(',', '.')
        # else: 1,234.56 formatı zaten uygun (ama Türkiye'de pek kullanılmaz)
    elif ',' in price_str: # Sadece virgül varsa ondalık ayıracı kabul et
         price_str = price_str.replace(',', '.')
    
    try:
        return float(price_str)
    except ValueError:
        return None

def find_columns_in_excel(df):
    """Locate common columns within an Excel ``DataFrame``.

    Parameters
    ----------
    df : pandas.DataFrame
        Loaded Excel sheet.

    Returns
    -------
    tuple
        ``(code_col, desc_col, price_col, currency_col)`` representing the
        column names if found, otherwise ``None`` for missing columns.
    """
    code_col = desc_col = price_col = currency_col = None
    df_columns_lower = [str(col).lower() for col in df.columns]

    for header in POSSIBLE_CODE_HEADERS:
        if header in df_columns_lower:
            code_col = df.columns[df_columns_lower.index(header)]
            break

    for header in POSSIBLE_DESCRIPTION_HEADERS:
        if header in df_columns_lower:
            desc_col = df.columns[df_columns_lower.index(header)]
            break

    for header in POSSIBLE_PRICE_HEADERS:
        if header in df_columns_lower:
            price_col = df.columns[df_columns_lower.index(header)]
            break

    for header in POSSIBLE_CURRENCY_HEADERS:
        if header in df_columns_lower:
            currency_col = df.columns[df_columns_lower.index(header)]
            break

    return code_col, desc_col, price_col, currency_col

# --- Veri Çıkarma Fonksiyonları ---

def extract_from_excel(filepath):
    """Extract product information from an Excel workbook.

    Parameters
    ----------
    filepath : str
        Path to the Excel file on disk.

    Returns
    -------
    pandas.DataFrame
        DataFrame in a unified format with ``material_code``, ``description``,
        ``price`` and auxiliary information. Returns an empty ``DataFrame`` if
        nothing could be parsed.
    """
    all_data = []
    year_match = re.search(r'(20\d{2})', os.path.basename(filepath))
    year = year_match.group(1) if year_match else None
    try:
        xls = pd.ExcelFile(filepath)
        for sheet_name in xls.sheet_names:
            try:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                if df.empty:
                    continue

                code_col, desc_col, price_col, currency_col = find_columns_in_excel(df)
                if not any([code_col, desc_col, price_col]):
                    continue

                sheet = pd.DataFrame()
                if code_col:
                    sheet['material_code'] = df[code_col]
                elif desc_col:
                    sheet['material_code'] = df[desc_col]
                else:
                    sheet['material_code'] = None

                if desc_col:
                    sheet['description'] = df[desc_col]
                elif code_col:
                    sheet['description'] = df[code_col]
                else:
                    sheet['description'] = None

                if price_col:
                    sheet['price'] = df[price_col].apply(clean_price)
                else:
                    sheet['price'] = None

                if currency_col:
                    sheet['price_currency'] = df[currency_col]
                else:
                    sheet['price_currency'] = '€'

                sheet['source_file'] = os.path.basename(filepath)
                sheet['source_page'] = sheet_name
                sheet['year'] = year

                all_data.append(sheet)

            except Exception as e_sheet:
                print(f"Excel sayfası ({filepath} - {sheet_name}) işlenirken hata: {e_sheet}")

        if not all_data:
            return pd.DataFrame(columns=['material_code','description','price','price_currency','source_file','source_page','year'])

        combined_df = pd.concat(all_data, ignore_index=True)
        if 'price' in combined_df.columns:
            combined_df = combined_df.dropna(subset=['price'])
        combined_df['price_currency'].fillna('€', inplace=True)
        return combined_df[['material_code','description','price','price_currency','source_file','source_page','year']]

    except Exception as e:
        print(f"Excel dosyası ({filepath}) işlenirken hata: {e}")
        return pd.DataFrame(columns=['material_code','description','price','price_currency','source_file','source_page','year'])

def extract_from_pdf(filepath):
    """Extract product information from a PDF file.

    The returned DataFrame is normalised to have the columns
    ``material_code``, ``description``, ``price``, ``price_currency``,
    ``source_file``, ``source_page`` and ``year``.
    """
    rows = []
    year_match = re.search(r'(20\d{2})', os.path.basename(filepath))
    year = year_match.group(1) if year_match else None

    line_pattern = re.compile(
        r'^(.*?)\s{2,}([\d\.,]+)\s*(TL|TRY|EUR|USD|\$|€)?$', re.IGNORECASE)

    try:
        with pdfplumber.open(filepath) as pdf:
            for page_idx, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ''
                for line in text.split('\n'):
                    line = line.strip()
                    m = line_pattern.match(line)
                    if not m:
                        continue

                    name = re.sub(r'\s{2,}', ' ', m.group(1)).strip()
                    price = clean_price(m.group(2))
                    currency = m.group(3) if m.group(3) else '€'

                    if not name or price is None:
                        continue

                    rows.append({
                        'material_code': name,
                        'description': name,
                        'price': price,
                        'price_currency': currency,
                        'source_file': os.path.basename(filepath),
                        'source_page': page_idx,
                        'year': year
                    })
    except Exception as e:
        print(f"PDF dosyası ({filepath}) işlenirken genel hata: {e}")
        return pd.DataFrame(columns=['material_code','description','price','price_currency','source_file','source_page','year'])

    return pd.DataFrame(rows, columns=['material_code','description','price','price_currency','source_file','source_page','year'])


# --- Ana İşlem ---
def main():
    """Entry point for the GUI based price extraction utility.

    This function prompts the user to select Excel or PDF files, invokes the
    appropriate extraction routines and finally saves the consolidated result
    to an Excel file chosen by the user.
    """
    root = tk.Tk()
    root.withdraw() # Ana tkinter penceresini göstermiyoruz

    messagebox.showinfo("Başlangıç", "Fiyat listelerini (Excel veya PDF) seçin.")
    filepaths = filedialog.askopenfilenames(
        title="Fiyat Listelerini Seçin",
        filetypes=(("Excel Dosyaları", "*.xlsx *.xls"),
                   ("PDF Dosyaları", "*.pdf"),
                   ("Tüm Dosyalar", "*.*"))
    )

    if not filepaths:
        messagebox.showinfo("İptal", "Dosya seçilmedi. İşlem iptal edildi.")
        return

    all_extracted_data = []
    for filepath in filepaths:
        filename = os.path.basename(filepath)
        print(f"\nİşleniyor: {filename}")
        
        if filename.lower().endswith(('.xlsx', '.xls')):
            df = extract_from_excel(filepath)
        elif filename.lower().endswith('.pdf'):
            df = extract_from_pdf(filepath)
        else:
            print(f"  Desteklenmeyen dosya türü: {filename}. Atlanıyor.")
            continue
        
        if not df.empty:
            print(f"  {filename} dosyasından {len(df)} kayıt çıkarıldı.")
            all_extracted_data.append(df)
        else:
            print(f"  {filename} dosyasından veri çıkarılamadı veya dosya boş.")

    if not all_extracted_data:
        messagebox.showinfo("Sonuç", "Hiçbir dosyadan veri çıkarılamadı.")
        return

    master_df = pd.concat(all_extracted_data, ignore_index=True)

    # Basic data cleanup
    master_df.dropna(subset=['Malzeme_Adi', 'Fiyat'], inplace=True)
    master_df['Malzeme_Adi'] = master_df['Malzeme_Adi'].astype(str).str.strip().str.upper()
    master_df = master_df[master_df['Malzeme_Adi'] != '']  # drop empty product names
    master_df['Fiyat'] = pd.to_numeric(master_df['Fiyat'], errors='coerce')
    master_df.dropna(subset=['Fiyat'], inplace=True)

    # Remove duplicates; keep the last occurrence
    master_df.drop_duplicates(subset=['Malzeme_Adi'], keep='last', inplace=True)
    # Optionally drop zero or near-zero prices
    master_df = master_df[master_df['Fiyat'] > 0.01] 

    # Sort for nicer output
    master_df.sort_values(by="Malzeme_Adi", inplace=True)


    if master_df.empty:
        messagebox.showinfo("Sonuç", "Veri çıkarıldı ancak temizlik sonrası geçerli kayıt kalmadı.")
        return
        
    output_filepath = filedialog.asksaveasfilename(
        title="Birleştirilmiş Excel Dosyasını Kaydet",
        defaultextension=".xlsx",
        filetypes=(("Excel Dosyası", "*.xlsx"),)
    )

    if output_filepath:
        try:
            master_df.to_excel(output_filepath, index=False)
            messagebox.showinfo("Başarılı", f"{len(master_df)} kayıt başarıyla '{output_filepath}' dosyasına kaydedildi.")
            print(f"\n{len(master_df)} kayıt başarıyla '{output_filepath}' dosyasına kaydedildi.")
        except Exception as e:
            messagebox.showerror("Kaydetme Hatası", f"Dosya kaydedilemedi: {e}")
            print(f"Dosya kaydedilemedi: {e}")
    else:
        messagebox.showinfo("İptal", "Kaydetme işlemi iptal edildi.")

if __name__ == "__main__":
    main()
