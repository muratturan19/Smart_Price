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
    """Fiyat string'ini temizleyip float'a çevirir."""
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
    """DataFrame'de ürün adı ve fiyat sütunlarını bulmaya çalışır."""
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
    """Excel dosyasından malzeme adı ve fiyat bilgilerini çıkarır."""
    all_data = []
    try:
        # Birden fazla sayfa olabileceği için tüm sayfaları deneyelim
        xls = pd.ExcelFile(filepath)
        for sheet_name in xls.sheet_names:
            try:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                if df.empty:
                    continue

                product_col, price_col = find_columns_in_excel(df)
                
                # Sütunlar bulunamadıysa kullanıcıdan isteyelim
                if not product_col:
                    product_col_name_or_idx = simpledialog.askstring("Eksik Bilgi", 
                        f"{filepath} - '{sheet_name}' sayfasında\n"
                        f"MALZEME ADI/KODU sütununun tam adını veya\n"
                        f"indeksini (0'dan başlayarak, örn: A için 0, B için 1) girin:",
                        initialvalue=df.columns[0] if len(df.columns) > 0 else "0" )
                    if not product_col_name_or_idx: return pd.DataFrame() # Kullanıcı iptal etti
                    try: product_col = df.columns[int(product_col_name_or_idx)]
                    except ValueError: product_col = product_col_name_or_idx
                    except IndexError: product_col = product_col_name_or_idx


                if not price_col:
                    price_col_name_or_idx = simpledialog.askstring("Eksik Bilgi",
                        f"{filepath} - '{sheet_name}' sayfasında\n"
                        f"FİYAT sütununun tam adını veya\n"
                        f"indeksini (0'dan başlayarak) girin:",
                        initialvalue=df.columns[1] if len(df.columns) > 1 else "1")
                    if not price_col_name_or_idx: return pd.DataFrame() # Kullanıcı iptal etti
                    try: price_col = df.columns[int(price_col_name_or_idx)]
                    except ValueError: price_col = price_col_name_or_idx
                    except IndexError: price_col = price_col_name_or_idx


                if product_col not in df.columns or price_col not in df.columns:
                    messagebox.showwarning("Sütun Bulunamadı", f"{filepath} - '{sheet_name}' sayfasında belirtilen sütunlar bulunamadı. Bu sayfa atlanıyor.")
                    continue

                # Veriyi çek
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
    """
    PDF dosyasından malzeme adı ve fiyat bilgilerini çıkarmaya çalışır.
    BU KISIM PDF'İN YAPISINA GÖRE ÖNEMLİ ÖLÇÜDE ÖZELLEŞTİRME GEREKTİREBİLİR.
    """
    data = []
    # --- PDF PARSING STRATEJİLERİ ---
    # PDF'ler çok çeşitli olduğu için birden fazla strateji/regex gerekebilir.
    # Örnek Regex'ler (bunları PDF yapınıza göre düzenlemeniz GEREKİR):
    #     Desen 1: "ÜRÜN KODU/ADI ... FİYAT TL" (arada çok şey olabilir)
    #         ^(.*?)\s+[.\s]*?([\d,\.]+)\s*(?:TL|TRY|EUR|USD|\$|€)\s*$
    #     Desen 2: Satır başında ürün kodu/adı, satır sonunda fiyat
    #         ^([A-Z0-9\s\-\/]+?)\s+.*\s+([\d,\.]+)\s*(?:TL|TRY)?$
    #     Desen 3: Tablo benzeri yapılar için (çok genel, dikkatli olunmalı)
    #         Bir satırda hem harf/rakam (ürün) hem de sayı (fiyat) arama
    #         Bu çok fazla yanlış pozitif verebilir.
    #
    # KULLANICI TARAFINDAN TANIMLANABİLİR REGEX'LER ÖNEMLİ OLACAKTIR
    # Şimdilik çok genel bir yaklaşım:
    
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
                        # Tablodan sütunları anlamlandırmak çok zor.
                        # Kullanıcıdan hangi sütunların ürün adı/fiyat olduğunu sormak gerekebilir.
                        # Şimdilik basit bir varsayım: ilk metin sütunu ürün, son sayısal sütun fiyat.
                        # Bu çok hatalı olabilir!
                        try:
                            df_table = pd.DataFrame(table)
                            # Baştaki boş None satırları atla (eğer varsa)
                            df_table.dropna(how='all', inplace=True)
                            # İlk geçerli satırı başlık olarak almayı dene (eğer ilk satır başlık değilse sorun olur)
                            # if df_table.iloc[0].notna().all(): # Eğer ilk satır doluysa başlık kabul et
                            #     df_table.columns = df_table.iloc[0]
                            #     df_table = df_table[1:]

                            # Çok basit bir tablo mantığı:
                            # İlk sütun veya içinde 'kod'/'ad' geçen sütun ürün, son sütun veya içinde 'fiyat' geçen sütun fiyat
                            # Bu kısım çok daha zeki olmalı veya kullanıcı girdisi almalı
                            product_col_idx = 0
                            price_col_idx = -1 # Sondan birinci

                            # Deneme: Başlık varsa sütun bul
                            if any(str(c).lower() in POSSIBLE_PRODUCT_NAME_HEADERS for c in df_table.columns):
                                product_col_idx = [idx for idx, c in enumerate(df_table.columns) if str(c).lower() in POSSIBLE_PRODUCT_NAME_HEADERS][0]
                            if any(str(c).lower() in POSSIBLE_PRICE_HEADERS for c in df_table.columns):
                                price_col_idx = [idx for idx, c in enumerate(df_table.columns) if str(c).lower() in POSSIBLE_PRICE_HEADERS][0]

                            for _, row in df_table.iterrows():
                                product_name = str(row.iloc[product_col_idx]).strip() if len(row) > product_col_idx and row.iloc[product_col_idx] else None
                                price_str = str(row.iloc[price_col_idx]).strip() if len(row) > abs(price_col_idx) and row.iloc[price_col_idx] else None
                                
                                if product_name and price_str and len(product_name) > 2: # Temel bir filtreleme
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

    # Temel veri temizliği
    master_df.dropna(subset=['Malzeme_Adi', 'Fiyat'], inplace=True)
    master_df['Malzeme_Adi'] = master_df['Malzeme_Adi'].astype(str).str.strip().str.upper()
    master_df = master_df[master_df['Malzeme_Adi'] != ''] # Boş malzeme adlarını sil
    master_df['Fiyat'] = pd.to_numeric(master_df['Fiyat'], errors='coerce')
    master_df.dropna(subset=['Fiyat'], inplace=True)

    # Mükerrer ürünler için: sonuncuyu tut (veya ilkini 'first', ya da ortalama al vs.)
    master_df.drop_duplicates(subset=['Malzeme_Adi'], keep='last', inplace=True)
    # Fiyatı 0 olanları veya çok düşük olanları isteğe bağlı filtrele
    master_df = master_df[master_df['Fiyat'] > 0.01] 

    # Sıralama
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
