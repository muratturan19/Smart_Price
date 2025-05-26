import pandas as pd
import pdfplumber
import os
import re
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox

# --- Konfigürasyon ve Yardımcı Fonksiyonlar ---

# Malzeme adı/kodu için arayabileceğimiz yaygın sütun başlıkları (Excel için)
POSSIBLE_PRODUCT_NAME_HEADERS = [
    'ürün adı', 'malzeme adı', 'ürün kodu', 'malzeme kodu', 'kod', 'product name', 'product code', 'material code', 'item name', 'description'
]
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
    """Locate product name and price columns within an Excel ``DataFrame``.

    Parameters
    ----------
    df : pandas.DataFrame
        Loaded Excel sheet.

    Returns
    -------
    tuple
        ``(product_col, price_col)`` representing the column names if found,
        otherwise ``None`` for missing columns.
    """
    product_col, price_col = None, None
    df_columns_lower = [str(col).lower() for col in df.columns]

    for header in POSSIBLE_PRODUCT_NAME_HEADERS:
        if header in df_columns_lower:
            product_col = df.columns[df_columns_lower.index(header)]
            break
    
    for header in POSSIBLE_PRICE_HEADERS:
        if header in df_columns_lower:
            price_col = df.columns[df_columns_lower.index(header)]
            break
    return product_col, price_col

# --- Veri Çıkarma Fonksiyonları ---

def extract_from_excel(filepath):
    """Extract product names and prices from an Excel workbook.

    Parameters
    ----------
    filepath : str
        Path to the Excel file on disk.

    Returns
    -------
    pandas.DataFrame
        DataFrame containing ``Malzeme_Adi`` and ``Fiyat`` columns. Returns an
        empty ``DataFrame`` if nothing could be parsed.
    """
    all_data = []
    try:
        # Try every sheet as workbooks may contain multiple pages
        xls = pd.ExcelFile(filepath)
        for sheet_name in xls.sheet_names:
            try:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                if df.empty:
                    continue

                product_col, price_col = find_columns_in_excel(df)
                
                # Ask the user for column names if automatic detection fails
                if not product_col:
                    product_col_name_or_idx = simpledialog.askstring("Eksik Bilgi", 
                        f"{filepath} - '{sheet_name}' page\n"
                        f"Enter the exact PRODUCT NAME/CODE column name or\n"
                        f"its index (0-based, e.g. 0 for A, 1 for B):",
                        initialvalue=df.columns[0] if len(df.columns) > 0 else "0" )
                    if not product_col_name_or_idx: return pd.DataFrame() # Kullanıcı iptal etti
                    try: product_col = df.columns[int(product_col_name_or_idx)]
                    except ValueError: product_col = product_col_name_or_idx
                    except IndexError: product_col = product_col_name_or_idx


                if not price_col:
                    price_col_name_or_idx = simpledialog.askstring("Eksik Bilgi",
                        f"{filepath} - '{sheet_name}' page\n"
                        f"Enter the exact PRICE column name or its index (0-based):",
                        initialvalue=df.columns[1] if len(df.columns) > 1 else "1")
                    if not price_col_name_or_idx: return pd.DataFrame() # Kullanıcı iptal etti
                    try: price_col = df.columns[int(price_col_name_or_idx)]
                    except ValueError: price_col = price_col_name_or_idx
                    except IndexError: price_col = price_col_name_or_idx


                if product_col not in df.columns or price_col not in df.columns:
                    messagebox.showwarning(
                        "Column Missing",
                        f"{filepath} - '{sheet_name}' page does not contain the specified columns. Skipping this sheet."
                    )
                    continue

                # Extract data from the detected columns
                sheet_data = df[[product_col, price_col]].copy()
                sheet_data.columns = ['Malzeme_Adi', 'Fiyat_Ham']
                all_data.append(sheet_data)

            except Exception as e_sheet:
                print(f"Excel sayfası ({filepath} - {sheet_name}) işlenirken hata: {e_sheet}")
        
        if not all_data:
            return pd.DataFrame()
        
        combined_df = pd.concat(all_data, ignore_index=True)
        combined_df['Fiyat'] = combined_df['Fiyat_Ham'].apply(clean_price)
        return combined_df[['Malzeme_Adi', 'Fiyat']].dropna()

    except Exception as e:
        print(f"Excel dosyası ({filepath}) işlenirken hata: {e}")
        return pd.DataFrame()

def extract_from_pdf(filepath):
    """Extract product information from a PDF file.

    Parameters
    ----------
    filepath : str
        Path to the PDF document.

    Returns
    -------
    pandas.DataFrame
        DataFrame with ``Malzeme_Adi`` and ``Fiyat`` columns. The extraction
        heuristics depend heavily on the PDF layout and may require
        adjustments for different documents.
    """
    data = []
    # --- PDF PARSING STRATEGIES ---
    # PDFs can vary greatly in structure. Below we define a few regular
    # expressions that attempt to capture common patterns. These may need to be
    # customised for different documents:
    #   Pattern 1: "PRODUCT CODE/NAME ... PRICE TL" with arbitrary text in
    #              between.
    #       ^(.*?)\s+[.\s]*?([\d,\.]+)\s*(?:TL|TRY|EUR|USD|\$|€)\s*$
    #   Pattern 2: Product code/name at the beginning of the line and price at
    #              the end.
    #       ^([A-Z0-9\s\-\/]+?)\s+.*\s+([\d,\.]+)\s*(?:TL|TRY)?$
    #   Pattern 3: A very generic table-like structure; may produce many false
    #              positives.
    #       search a line for any alphanumeric text followed by a number.
    # Users may provide their own patterns depending on the PDF layout.
    
    # Regex: (Malzeme Adı/Kodu Grubu) ..... (Fiyat Grubu) [Para Birimi İsteğe Bağlı]
    # Bu regex'ler çok geneldir ve PDF'lerinize göre iyileştirilmesi gerekir.
    # Grup 1: Malzeme Adı/Kodu (agresif olmayan, boşluktan sonraki sayısal kısma kadar)
    # Grup 2: Fiyat (sayısal, virgül veya nokta içerebilir)
    patterns = [
        re.compile(r'^(.*?)\s{2,}([\d\.,]+)\s*(?:TL|TRY|EUR|USD|\$|€)?$', re.MULTILINE | re.IGNORECASE), # Genellikle iki veya daha fazla boşlukla ayrılmış
        re.compile(r'([A-Z0-9\-\s/]{5,50})\s+([\d\.,]+)\s*(?:TL|TRY|EUR|USD|\$|€)?', re.IGNORECASE), # Belirli uzunlukta bir ürün adı/kodu ve fiyat
        re.compile(r'Item Code:\s*(.*?)\s*Price:\s*([\d\.,]+)', re.IGNORECASE),
        re.compile(r'Ürün No:\s*(.*?)\s*Birim Fiyat:\s*([\d\.,]+)', re.IGNORECASE),
    ]

    try:
        with pdfplumber.open(filepath) as pdf:
            for i, page in enumerate(pdf.pages):
                print(f"  PDF Sayfası {i+1} işleniyor...")
                text = page.extract_text()
                
                if not text: # Resim tabanlı olabilir, OCR gerekir (bu scriptte yok)
                    print(f"    Sayfa {i+1} metin içermiyor veya çıkarılamadı (Resim olabilir).")
                    # Gelişmiş: Tabloları çıkarmayı dene
                    tables = page.extract_tables()
                    for table_num, table in enumerate(tables):
                        print(f"    Sayfa {i+1}, Tablo {table_num+1} deneniyor...")
                        if not table: continue
                        # Interpreting table columns is tricky. Ideally the
                        # user should specify which columns represent product
                        # names and prices. As a naive assumption we take the
                        # first textual column as the product and the last
                        # numeric column as the price. This may easily fail.
                        try:
                            df_table = pd.DataFrame(table)
                            # Drop completely empty rows if present
                            df_table.dropna(how='all', inplace=True)
                            # Attempt to use the first non-empty row as a
                            # header when appropriate.
                            # if df_table.iloc[0].notna().all():
                            #     df_table.columns = df_table.iloc[0]
                            #     df_table = df_table[1:]

                            # Very naive table heuristic:
                            # choose the first column (or the one containing
                            # keywords such as 'code' or 'name') as the product
                            # and the last column (or the one containing the
                            # word 'price') as the price. A smarter
                            # implementation or user input would be better.
                            product_col_idx = 0
                            price_col_idx = -1  # last column by default

                            # Try to detect columns based on headers when
                            # available
                            if any(str(c).lower() in POSSIBLE_PRODUCT_NAME_HEADERS for c in df_table.columns):
                                product_col_idx = [idx for idx, c in enumerate(df_table.columns) if str(c).lower() in POSSIBLE_PRODUCT_NAME_HEADERS][0]
                            if any(str(c).lower() in POSSIBLE_PRICE_HEADERS for c in df_table.columns):
                                price_col_idx = [idx for idx, c in enumerate(df_table.columns) if str(c).lower() in POSSIBLE_PRICE_HEADERS][0]

                            for _, row in df_table.iterrows():
                                product_name = str(row.iloc[product_col_idx]).strip() if len(row) > product_col_idx and row.iloc[product_col_idx] else None
                                price_str = str(row.iloc[price_col_idx]).strip() if len(row) > abs(price_col_idx) and row.iloc[price_col_idx] else None
                                
                                # Basic sanity checks: require both fields and
                                # a reasonable product name length
                                if product_name and price_str and len(product_name) > 2:
                                    price = clean_price(price_str)
                                    if price is not None:
                                        data.append({'Malzeme_Adi': product_name, 'Fiyat': price})
                                        print(f"      Tablodan bulundu: {product_name} - {price}")
                        except Exception as e_table:
                            print(f"      Tablo işleme hatası: {e_table}")
                    continue # Şimdilik tablodan sonra metin aramayı geç


                # Metin tabanlı arama
                lines = text.split('\n')
                found_on_page = False
                for line_num, line in enumerate(lines):
                    line = line.strip()
                    if len(line) < 5: continue # Çok kısa satırları atla

                    for pattern_idx, pattern in enumerate(patterns):
                        matches = pattern.findall(line)
                        if not matches and pattern_idx == 0 and len(line.split()) > 1: # İlk regex için özel: tüm satırı dene
                             match_obj = pattern.match(line)
                             if match_obj:
                                 matches = [match_obj.groups()]

                        for match in matches:
                            # Regex'e göre match bir tuple olabilir (grup1, grup2)
                            if len(match) == 2:
                                product_name = str(match[0]).strip()
                                price_str = str(match[1]).strip()
                                
                                # Temizlik
                                product_name = re.sub(r'\s{2,}', ' ', product_name) # Fazla boşlukları tek boşluğa indir
                                if not product_name or len(product_name) < 3: # Çok kısa ürün adlarını atla
                                    continue

                                price = clean_price(price_str)
                                if price is not None:
                                    data.append({'Malzeme_Adi': product_name, 'Fiyat': price})
                                    found_on_page = True
                                    print(f"    Regex {pattern_idx+1} ile bulundu: {product_name} - {price}")
                                    # break # Bir satırda bir eşleşme yeterli olabilir, sonraki satıra geç
                    # if found_on_page: break # Eğer bu satırda bulunduysa sonraki satır pattern'lerini deneme

                if not found_on_page:
                     print(f"    Sayfa {i+1} için metinden bilinen desenlerle eşleşme bulunamadı. Bu sayfa daha detaylı analiz gerektirebilir.")


    except Exception as e:
        messagebox.showerror("PDF Hatası", f"PDF dosyası ({filepath}) işlenirken genel hata: {e}")
        print(f"PDF dosyası ({filepath}) işlenirken genel hata: {e}")
    
    return pd.DataFrame(data)


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
