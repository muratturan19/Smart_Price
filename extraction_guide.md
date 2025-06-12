# Extraction Guide

---

## STEED FİYAT LİSTESİ

- **Her kalın ve büyük punto başlık**: `Ana_Baslik` (alt başlık yok, `Alt_Baslik` her zaman boş)
- Her ürün satırı için şu alanları çıkar:
  - Malzeme_Kodu
  - Açıklama
  - Kisa_Kod
  - Fiyat
  - Para_Birimi
  - Marka (her zaman "STEED")
  - Kaynak_Dosya (her zaman "Steed Fiyat Listesi 2025")
  - Sayfa
  - Record_Code (her zaman "STEED")
  - Ana_Baslik
  - Alt_Baslik (her zaman boş)
  - Image_Path

**Kural:**  
Alan yoksa boş bırak.  
Çıktı şu formatta olacak:

```json
{
  "Malzeme_Kodu": "...",
  "Açıklama": "...",
  "Kisa_Kod": "...",
  "Fiyat": "...",
  "Para_Birimi": "...",
  "Marka": "STEED",
  "Kaynak_Dosya": "Steed Fiyat Listesi 2025",
  "Sayfa": ...,
  "Record_Code": "STEED",
  "Ana_Baslik": "...",
  "Alt_Baslik": "",
  "Image_Path": ""
}

Dikkat!
PDF’deki tablo ve alan başlıkları çok farklı şekillerde yazılmış olabilir. Aşağıdaki tüm ifadeler benzer anlama gelir ve ilgili alan başlığına eşlenmelidir:
•	Malzeme_Kodu: ürün kodu, urun kodu, malzeme kodu, malzeme, stok kodu, kod, tip, ref no, ref., ürün ref, ürün tip, product code, part no, item name, item no, item number, item , ürün adı
•	Kısa_Kod: kisa kod, short code, shortcode, kısa ürün kodu
•	Açıklama/Özellikler: description, ürün açıklaması, açıklama, aciklama, özellikler, detay, product name, explanation
•	Fiyat: fiyat, birim fiyat, liste fiyatı, price, unit price, list price, tutar
•	Para_Birimi: para birimi, currency
•	Ana_Baslik: ana başlık, ana baslik, ana_baslik
•	Alt_Baslik: alt başlık, alt baslik, alt_baslik
Kurallar:
•	Tablodaki her ürün satırını, hiçbirini atlamadan, eksiksiz ve ayrı bir JSON objesi olarak çıkar.
•	Sadece başlıkları, alt başlıkları veya açıklama satırlarını dahil etme; sadece gerçek ürün satırlarını çıkar.
•	Sonuçları JSON formatında döndür.

Her başlık için doğru alan eşleşmesini yap. Hiçbir ürünü veya satırı atlama. Yalnızca istenen alanlar ve ürün satırları çıktıda yer almalı.

---

## ESMAKSAN FİYAT LİSTESİ

En üstteki büyük, kalın başlık: Ana_Baslik

Ürün bloklarının/tablolarının başlığı varsa: Alt_Baslik, yoksa boş

Her ürün satırı için şu alanları çıkar:

Malzeme_Kodu

Açıklama

Kisa_Kod

Fiyat

Para_Birimi

Marka (her zaman "ESMAKSAN")

Kaynak_Dosya (her zaman "ESMAKSAN 2025 MART FİYAT LİSTESİ.pdf")

Sayfa

Record_Code (her zaman "ESMAKSAN")

Ana_Baslik

Alt_Baslik

Image_Path

Kural:
Alan yoksa boş bırak.
Çıktı şu formatta olacak:

{
  "Malzeme_Kodu": "...",
  "Açıklama": "...",
  "Kisa_Kod": "...",
  "Fiyat": "...",
  "Para_Birimi": "...",
  "Marka": "ESMAKSAN",
  "Kaynak_Dosya": "ESMAKSAN 2025 MART FİYAT LİSTESİ.pdf",
  "Sayfa": ...,
  "Record_Code": "ESMAKSAN",
  "Ana_Baslik": "...",
  "Alt_Baslik": "...",
  "Image_Path": ""
}
Dikkat!
PDF’deki tablo ve alan başlıkları çok farklı şekillerde yazılmış olabilir. Aşağıdaki tüm ifadeler benzer anlama gelir ve ilgili alan başlığına eşlenmelidir:
•	Malzeme_Kodu: ürün kodu, urun kodu, malzeme kodu, malzeme, stok kodu, kod, tip, ref no, ref., ürün ref, ürün tip, product code, part no, item name, item no, item number, item , ürün adı
•	Kısa_Kod: kisa kod, short code, shortcode, kısa ürün kodu
•	Açıklama/Özellikler: description, ürün açıklaması, açıklama, aciklama, özellikler, detay, product name, explanation
•	Fiyat: fiyat, birim fiyat, liste fiyatı, price, unit price, list price, tutar
•	Para_Birimi: para birimi, currency
•	Ana_Baslik: ana başlık, ana baslik, ana_baslik
•	Alt_Baslik: alt başlık, alt baslik, alt_baslik
Kurallar:
•	Tablodaki her ürün satırını, hiçbirini atlamadan, eksiksiz ve ayrı bir JSON objesi olarak çıkar.
•	Sadece başlıkları, alt başlıkları veya açıklama satırlarını dahil etme; sadece gerçek ürün satırlarını çıkar.
•	Sonuçları JSON formatında döndür.

Her başlık için doğru alan eşleşmesini yap. Hiçbir ürünü veya satırı atlama. Yalnızca istenen alanlar ve ürün satırları çıktıda yer almalı.

---

## MATRIX Fiyat Listesi

### Genel Kural

- **Ana_Baslik:** Her sayfanın en üst sağ köşesindeki ana başlık (ör: `320 Series`)
- **Alt_Baslik:**  
  - Tablo blok başlığındaki mavi veya kalın/kutulu başlık (ör: `Model 321 | 3/2 | NC - NO`, `OPTIONS`, `ACCESSORIES`)
  - Tabloda başlık yoksa Alt_Baslik boş bırakılır.
- **Malzeme_Kodu:** Tablodaki PART NUMBER hücresindeki değer.
- **Açıklama:**  
  - Konfigürasyon/opsiyonun satır açıklaması veya satır başındaki teknik metin.
  - (Örneğin: `3/2 I NC I 28 l/min @ 6 bar I 0-8 bar I 24 VDC I NBR I IP52 Pico-Spox type male connector I subplate mounting`)
- **Fiyat:** Tablodaki EUR sütunundaki değer (örn: 40,00)
- **Para_Birimi:** Her zaman `"EUR"`
- **Marka:** `"MATRIX"`
- **Kaynak_Dosya:** `"MATRIX Fiyat Listesi 10.03.25.pdf"`
- **Sayfa:** Ürünün bulunduğu sayfa numarası (örn: 1)
- **Record_Code:** `"MATRIX"`
- **Kisa_Kod, Image_Path:** Eğer tablo veya satırda açıkça verilmemişse boş bırak.

### Çıktı Formatı

Aşağıdaki tüm alanları **her ürün satırı için** eksiksiz üret (yoksa boş bırak):

```json
{
  "Malzeme_Kodu": "...",
  "Açıklama": "...",
  "Kisa_Kod": "",
  "Fiyat": "...",
  "Para_Birimi": "EUR",
  "Marka": "MATRIX",
  "Kaynak_Dosya": "MATRIX Fiyat Listesi 10.03.25.pdf",
  "Sayfa": ...,
  "Record_Code": "MATRIX",
  "Ana_Baslik": "320 Series",
  "Alt_Baslik": "Model 321 | 3/2 | NC - NO",  // veya "OPTIONS", "ACCESSORIES" (blok başlığı)
  "Image_Path": ""
}

Dikkat!
PDF’deki tablo ve alan başlıkları çok farklı şekillerde yazılmış olabilir. Aşağıdaki tüm ifadeler benzer anlama gelir ve ilgili alan başlığına eşlenmelidir:
•	Malzeme_Kodu: ürün kodu, urun kodu, malzeme kodu, malzeme, stok kodu, kod, tip, ref no, ref., ürün ref, ürün tip, product code, part no, item name, item no, item number, item , ürün adı
•	Kısa_Kod: kisa kod, short code, shortcode, kısa ürün kodu
•	Açıklama/Özellikler: description, ürün açıklaması, açıklama, aciklama, özellikler, detay, product name, explanation
•	Fiyat: fiyat, birim fiyat, liste fiyatı, price, unit price, list price, tutar
•	Para_Birimi: para birimi, currency
•	Ana_Baslik: ana başlık, ana baslik, ana_baslik
•	Alt_Baslik: alt başlık, alt baslik, alt_baslik
Kurallar:
•	Tablodaki her ürün satırını, hiçbirini atlamadan, eksiksiz ve ayrı bir JSON objesi olarak çıkar.
•	Sadece başlıkları, alt başlıkları veya açıklama satırlarını dahil etme; sadece gerçek ürün satırlarını çıkar.
•	Sonuçları JSON formatında döndür.

Her başlık için doğru alan eşleşmesini yap. Hiçbir ürünü veya satırı atlama. Yalnızca istenen alanlar ve ürün satırları çıktıda yer almalı.

Ekstra Kural ve Notlar
Eğer herhangi bir alan ürün için mevcut değilse boş bırak.

Her ürün satırında Ana_Baslik ve Alt_Baslik mutlaka yer almalı.

Diğer tüm başlık, dipnot veya görsel satırları atla.

Sadece fiyat ve ürün kodu olan satırlar için çıkarım yap.

Her yeni sayfa veya tablo blok başlığı gördüğünde (ör: OPTIONS, ACCESSORIES), yeni Alt_Baslik ile devam et.
Ana_Baslik sayfanın en üst sağ köşesi ile değişiyorsa ona göre güncelle.

---

## GAMAK Fiyat Listesi (Örnek: 1 Fazlı Asenkron Motorlar PDF’i)

### Başlık Hiyerarşisi ve Kuralı

- PDF’de, **görsel olarak tam sayfa oluşturulmuş büyük başlıklarda**:
    - İlk ve en büyük puntolu, vurgulu başlık **Ana_Baslik** (örn: “1 Fazlı Asenkron Motorlar”)
    - Hemen altındaki, çoğu zaman şerit veya kutu gibi gözüken başlık **Alt_Baslik** (örn: “Monofaze Motorlar”)
- Bir ürün tablosu veya fiyat listesi, bu kapaktan 1 veya birkaç sayfa sonra başlasa bile,  
  **hemen üzerinde yeni başlık yoksa**, yukarıdan en yakın bu görsel başlıklar (Ana_Baslik + Alt_Baslik) kullanılır.
- Eğer ürün tablosunun hemen üstünde farklı bir teknik/grup başlığı (örn: “DAİMİ KONDANSATÖRLÜ MOTORLAR” veya “2 KUTUP 3000 d/d”) varsa,  
  bu yeni başlık **Alt_Baslik** olarak değerlendirilir; Ana_Baslik aynen kalır.
- Bir ürünün ait olduğu başlık grubu **daima yukarıya bakarak belirlenir**.


### Alanlar

Aşağıdaki her alanı **her ürün satırı için** doldur (yoksa boş bırak):

- Malzeme_Kodu: Ürün/model kodu (ör: “M22D 71 M 2a”)
- Açıklama: Varsa ürün açıklaması veya teknik satır (genellikle boş)
- Kisa_Kod: (Yoksa boş bırak)
- Fiyat: Ürün fiyatı (ör: “3.605”)
- Para_Birimi: “₺”
- Marka: “GAMAK”
- Kaynak_Dosya: (PDF dosya adı, ör: “MERA MOTOR-GAMAK 2025.pdf”)
- Sayfa: Ürünün yer aldığı sayfa no
- Record_Code: “GAMAK”
- Ana_Baslik: En büyük, görsel başlık (örn: “1 Fazlı Asenkron Motorlar”)
- Alt_Baslik: Hemen altındaki büyük/grup başlık veya ürün tablosunun hemen üstündeki teknik başlık (örn: “Monofaze Motorlar” veya “DAİMİ KONDANSATÖRLÜ MOTORLAR”)
- Image_Path: (Yoksa boş bırak)


### JSON Çıktı Formatı

```json
{
  "Malzeme_Kodu": "M22D 71 M 2a",
  "Açıklama": "",
  "Kisa_Kod": "",
  "Fiyat": "3.605",
  "Para_Birimi": "₺",
  "Marka": "GAMAK",
  "Kaynak_Dosya": "MERA MOTOR-GAMAK 2025.pdf",
  "Sayfa": 2,
  "Record_Code": "GAMAK",
  "Ana_Baslik": "1 Fazlı Asenkron Motorlar",
  "Alt_Baslik": "Monofaze Motorlar",
  "Image_Path": ""
}

Dikkat!
PDF’deki tablo ve alan başlıkları çok farklı şekillerde yazılmış olabilir. Aşağıdaki tüm ifadeler benzer anlama gelir ve ilgili alan başlığına eşlenmelidir:
•	Malzeme_Kodu: ürün kodu, urun kodu, malzeme kodu, malzeme, stok kodu, kod, tip, ref no, ref., ürün ref, ürün tip, product code, part no, item name, item no, item number, item , ürün adı
•	Kısa_Kod: kisa kod, short code, shortcode, kısa ürün kodu
•	Açıklama/Özellikler: description, ürün açıklaması, açıklama, aciklama, özellikler, detay, product name, explanation
•	Fiyat: fiyat, birim fiyat, liste fiyatı, price, unit price, list price, tutar
•	Para_Birimi: para birimi, currency
•	Ana_Baslik: ana başlık, ana baslik, ana_baslik
•	Alt_Baslik: alt başlık, alt baslik, alt_baslik
Kurallar:
•	Tablodaki her ürün satırını, hiçbirini atlamadan, eksiksiz ve ayrı bir JSON objesi olarak çıkar.
•	Sadece başlıkları, alt başlıkları veya açıklama satırlarını dahil etme; sadece gerçek ürün satırlarını çıkar.
•	Sonuçları JSON formatında döndür.

Her başlık için doğru alan eşleşmesini yap. Hiçbir ürünü veya satırı atlama. Yalnızca istenen alanlar ve ürün satırları çıktıda yer almalı.

---

## Omega Motor Tüm Fiyat Listeleri

### Başlık Yapısı ve Kuralı

- Her ürün tablosunun üstünde yer alan ana başlıklar doğrudan kullanılır.
    - En büyük, vurgulu başlık **Ana_Baslik** (ör: “IE3”, “IE4”)
    - Hemen altında genellikle kalın veya büyük puntolu olarak yazan, gövde/malzeme ve motor türünü belirten ifade **Alt_Baslik** (ör: “ALÜMİNYUM GÖVDELİ IEC 3~FAZLI ASENKRON ELEKTRİK MOTORLARI”, “PİK DÖKÜM GÖVDELİ”)
- Alt başlığın hemen altında teknik tanım veya hız grubu (örn: “2k-3000 d/dak.”, “4k-1500 d/dak.”, “6k-1000 d/dak.”) varsa, bu **Alt_Baslik2** veya **Açıklama** alanında ayrıca belirtilir.
- Her tablo satırı bir ürün kaydıdır.
- Eğer ürün satırı için birden fazla fiyat veya varyant varsa, aynı Malzeme_Kodu için fiyatları `-` ile ayırarak yaz.


### Alanlar

Her ürün satırı için doldurulacak alanlar:

- Malzeme_Kodu: Model kodu (ör: “3MAS 80MA2”)
- Açıklama: (örn: “2k-3000 d/dak.” gibi hız/grup bilgisi, yoksa boş bırak)
- Kisa_Kod: (yoksa boş bırak)
- Fiyat: Fiyat (ör: “128,00”)
- Para_Birimi: “USD”
- Marka: “OMEGA MOTOR”
- Kaynak_Dosya: “Omega Motor Tüm Fiyat Listeleri Mart 2025.pdf”
- Sayfa: Ürünün olduğu sayfa no
- Record_Code: “OMEGA”
- Ana_Baslik: (ör: “IE3”)
- Alt_Baslik: (ör: “ALÜMİNYUM GÖVDELİ IEC 3~FAZLI ASENKRON ELEKTRİK MOTORLARI” veya “PİK DÖKÜM GÖVDELİ”)
- Alt_Baslik2: (örn: “ALÜMİNYUM GÖVDELİ KOMPAKT MOTORLAR”)
- Image_Path: (yoksa boş bırak)


### JSON Çıktı Örneği

```json
{
  "Malzeme_Kodu": "3MAS 80MA2",
  "Açıklama": "2k-3000 d/dak.",
  "Kisa_Kod": "",
  "Fiyat": "110,00",
  "Para_Birimi": "USD",
  "Marka": "OMEGA MOTOR",
  "Kaynak_Dosya": "Omega Motor Tüm Fiyat Listeleri Mart 2025.pdf",
  "Sayfa": 1,
  "Record_Code": "OMEGA",
  "Ana_Baslik": "IE3",
  "Alt_Baslik": "ALÜMİNYUM GÖVDELİ IEC 3~FAZLI ASENKRON ELEKTRİK MOTORLARI",
  "Alt_Baslik2": "",
  "Image_Path": ""
}
Dikkat!
PDF’deki tablo ve alan başlıkları çok farklı şekillerde yazılmış olabilir. Aşağıdaki tüm ifadeler benzer anlama gelir ve ilgili alan başlığına eşlenmelidir:
•	Malzeme_Kodu: ürün kodu, urun kodu, malzeme kodu, malzeme, stok kodu, kod, tip, ref no, ref., ürün ref, ürün tip, product code, part no, item name, item no, item number, item , ürün adı
•	Kısa_Kod: kisa kod, short code, shortcode, kısa ürün kodu
•	Açıklama/Özellikler: description, ürün açıklaması, açıklama, aciklama, özellikler, detay, product name, explanation
•	Fiyat: fiyat, birim fiyat, liste fiyatı, price, unit price, list price, tutar
•	Para_Birimi: para birimi, currency
•	Ana_Baslik: ana başlık, ana baslik, ana_baslik
•	Alt_Baslik: alt başlık, alt baslik, alt_baslik
Kurallar:
•	Tablodaki her ürün satırını, hiçbirini atlamadan, eksiksiz ve ayrı bir JSON objesi olarak çıkar.
•	Sadece başlıkları, alt başlıkları veya açıklama satırlarını dahil etme; sadece gerçek ürün satırlarını çıkar.
•	Sonuçları JSON formatında döndür.

Her başlık için doğru alan eşleşmesini yap. Hiçbir ürünü veya satırı atlama. Yalnızca istenen alanlar ve ürün satırları çıktıda yer almalı.

---

## Rekorsan-Fiyat Listesi

### Başlık ve Kural

- Her ürün tablosunun üstündeki blok başlık **Ana_Baslik** olarak alınır:
    - Örn: “BSP İÇE HAVŞA DÜZ HORTUM RAKORLARI” veya “BSP İÇE HAVŞA 90° HORTUM RAKORLARI”
- **Alt_Baslik** kullanılmaz; her zaman boş bırakılır.
- Tablodaki her satır bir ürün kaydıdır.
- Kolonlar: Malzeme Kodu, Hortum Ölçüsü, Somun Ölçüsü, Fiyat [TL], Kutu Adedi
- Kisa_Kod, Image_Path ve ek alanlar yoksa boş bırakılır.


### Alanlar

Her ürün satırı için çıkarılacak alanlar:

- Malzeme_Kodu: (ör: “RK-0613-RİSD”)
- Açıklama: (yoksa boş bırak)
- Kisa_Kod: (yoksa boş bırak)
- Fiyat: (ör: “42,21”)
- Para_Birimi: “₺”
- Marka: “REKORSAN”
- Kaynak_Dosya: “Rekorsan-Fiyat Listesi-27.01.2025.pdf”
- Sayfa: Ürünün olduğu sayfa no
- Record_Code: “REKORSAN”
- Ana_Baslik: Tablonun üstündeki başlık (örn: “BSP İÇE HAVŞA DÜZ HORTUM RAKORLARI”)
- Alt_Baslik: (“” — her zaman boş)
- Image_Path: (yoksa boş bırak)


### JSON Çıktı Örneği

```json
{
  "Malzeme_Kodu": "RK-0613-RİSD",
  "Açıklama": "",
  "Kisa_Kod": "",
  "Fiyat": "42,21",
  "Para_Birimi": "₺",
  "Marka": "REKORSAN",
  "Kaynak_Dosya": "Rekorsan-Fiyat Listesi-27.01.2025.pdf",
  "Sayfa": 1,
  "Record_Code": "REKORSAN",
  "Ana_Baslik": "BSP İÇE HAVŞA DÜZ HORTUM RAKORLARI",
  "Alt_Baslik": "",
  "Image_Path": ""
}

Dikkat!
PDF’deki tablo ve alan başlıkları çok farklı şekillerde yazılmış olabilir. Aşağıdaki tüm ifadeler benzer anlama gelir ve ilgili alan başlığına eşlenmelidir:
•	Malzeme_Kodu: ürün kodu, urun kodu, malzeme kodu, malzeme, stok kodu, kod, tip, ref no, ref., ürün ref, ürün tip, product code, part no, item name, item no, item number, item , ürün adı
•	Kısa_Kod: kisa kod, short code, shortcode, kısa ürün kodu
•	Açıklama/Özellikler: description, ürün açıklaması, açıklama, aciklama, özellikler, detay, product name, explanation
•	Fiyat: fiyat, birim fiyat, liste fiyatı, price, unit price, list price, tutar
•	Para_Birimi: para birimi, currency
•	Ana_Baslik: ana başlık, ana baslik, ana_baslik
•	Alt_Baslik: alt başlık, alt baslik, alt_baslik
Kurallar:
•	Tablodaki her ürün satırını, hiçbirini atlamadan, eksiksiz ve ayrı bir JSON objesi olarak çıkar.
•	Sadece başlıkları, alt başlıkları veya açıklama satırlarını dahil etme; sadece gerçek ürün satırlarını çıkar.
•	Sonuçları JSON formatında döndür.

Her başlık için doğru alan eşleşmesini yap. Hiçbir ürünü veya satırı atlama. Yalnızca istenen alanlar ve ürün satırları çıktıda yer almalı.
