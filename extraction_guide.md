# LLM PDF Price List Extraction – Unified Guide (v2, 13 Jun 2025)

> **IMPORTANT**: Section 0 applies to **every** prompt. Brand sections only add or override details.

---

## 0 · GLOBAL OUTPUT CONTRACT  \(🟥 MUST FOLLOW\)

1. **Always produce JSON**. Your first instruction sentence MUST include the word **"JSON"**.
2. Wrap every result in a single root object with the key **`"products"`**:

   ```json
   {
     "products": [
       { …one product object… }
     ]
   }
   ```

   Return an *array* even if there is only **one** product.
3. Fields for every product object *(leave blank when not available)*:

   * `Malzeme_Kodu`
   * `Açıklama`
   * `Kisa_Kod`
   * `Fiyat`
   * `Para_Birimi`
   * `Marka`
   * `Kaynak_Dosya`
   * `Sayfa`
   * `Record_Code`
   * `Ana_Baslik`
   * `Alt_Baslik`
   * `Alt_Baslik2` *(optional; only when explicitly defined below)*
   * `Image_Path`
4. **Cleaning & Validation**

   * Strip *all* whitespace in `Malzeme_Kodu` \(e.g. `"M X 4 5 8S"` → `"MX458S"`\).
   * Preserve decimal separators exactly as printed.
   * Do **not** invent values; leave unknown fields `""`.
   * The final JSON must pass `json.loads()` and satisfy the above schema.
   * Part number hücresindeki tüm alfasayısal parçaları boşluksuz birleştir (ör. `M X B 9 9 ... → MXB9910...`).

---

## 1 · UNIVERSAL SYNONYM MAP

| Canonical Field   | Accept any of these header texts                                                                                                                           |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Malzeme\_Kodu** | ürün kodu, urun kodu, malzeme kodu, malzeme, stok kodu, kod, tip, ref no, ref., ürün ref, ürün tip, product code, part number, part no, item name, item no, item number |
| **Kisa\_Kod**     | kisa kod, short code, shortcode, kısa ürün kodu                                                                                                            |
| **Açıklama**      | description, ürün açıklaması, açıklama, aciklama, özellikler, detay, product name, explanation                                                             |
| **Fiyat**         | fiyat, birim fiyat, liste fiyatı, price, unit price, list price, tutar                                                                                     |
| **Para_Birimi**  | para birimi, currency, eur, usd, try, gbp                                                                                                                                      |
| **Ana\_Baslik**   | ana başlık, ana baslik, ana\_baslik                                                                                                                        |
| **Alt\_Baslik**   | alt başlık, alt baslik, alt\_baslik                                                                                                                        |

For any synonym **not** listed here, map it to the closest canonical field following the same logic.

---

## 2 · GENERAL EXTRACTION RULES

1. **Do not drop rows**: extract every real product row appearing in a table.
2. Exclude pure header / sub-‑header / footnote / image rows.
3. `Ana_Baslik` & `Alt_Baslik` must be populated for every product, using nearest visual headers as defined per brand.
4. For tables split across pages, continue using the last valid headers until a new header appears.
5. When a price list contains multiple currencies, set the value found in the currency column; otherwise use the brand default.

---

## 3 · BRAND‑SPECIFIC PROMPTS

Only the **differences** from Sections 0‑2 are listed below.

### 3.1 STEED

* Constants: `Marka = "STEED"`, `Kaynak_Dosya = "Steed Fiyat Listesi 2025"`, `Record_Code = "STEED"`
* `Ana_Baslik`: every bold, large heading on the page.
  `Alt_Baslik`: always `""`.

### 3.2 ESMAKSAN

* Constants: `Marka = "ESMAKSAN"`, `Kaynak_Dosya = "ESMAKSAN 2025 MART FİYAT LİSTESİ.pdf"`, `Record_Code = "ESMAKSAN"`
* `Ana_Baslik`: topmost large heading per page.
  `Alt_Baslik`: title of each table block if present, else `""`.

### 3.3 MATRIX

* Constants: `Marka = "MATRIX"`, `Kaynak_Dosya = "MATRIX Fiyat Listesi 10.03.25.pdf"`, `Record_Code = "MATRIX"`, `Para_Birimi = "EUR"`
* `Ana_Baslik`: page-header series name (e.g. `"320 Series"`).
* `Alt_Baslik`: table block title (e.g. `"Model 321 | 3/2 | NC - NO"`, `"OPTIONS"`, `"ACCESSORIES"`). Blank if none.
* If the right-header (e.g. "320 Series") repeats on following pages, keep the previous Ana_Baslik until a new right-header appears.
* Treat "OPTIONS" and "ACCESSORIES" captions as valid Alt_Baslik values; extract rows beneath them exactly like CONFIGURATIONS.

### 3.4 GAMAK

* Constants: `Marka = "GAMAK"`, `Kaynak_Dosya`: PDF file name, `Record_Code = "GAMAK"`, `Para_Birimi = "₺"`
* Header hierarchy: largest page title ➜ `Ana_Baslik`; second-level bold header ➜ `Alt_Baslik`.

### 3.5 OMEGA MOTOR

* Constants: `Marka = "OMEGA MOTOR"`, `Kaynak_Dosya = "Omega Motor Tüm Fiyat Listeleri Mart 2025.pdf"`, `Record_Code = "OMEGA"`, `Para_Birimi = "USD"`
* Supports optional `Alt_Baslik2` when an additional speed/material line exists directly under `Alt_Baslik`.

### 3.6 REKORSAN

* Constants: `Marka = "REKORSAN"`, `Kaynak_Dosya = "Rekorsan-Fiyat Listesi-27.01.2025.pdf"`, `Record_Code = "REKORSAN"`, `Para_Birimi = "₺"`
* `Alt_Baslik` is **always** `""`.

---

## 4 · DEFAULT / FALLBACK PROMPT

Use when the PDF filename does **not** match any brand section above.

1. Identify the two highest-level visual headings: first → `Ana_Baslik`; second → `Alt_Baslik` (may be `""`).
2. Detect currency symbol for `Para_Birimi`; default to `""` if none.
3. Leave `Marka`, `Record_Code`, and `Kaynak_Dosya` as `""`.
4. Follow Sections 0‑2 for all other rules.

---

## 5 · RETURN STATEMENT TEMPLATE (insert verbatim at the end of every prompt)

```
Aşağıdaki yönergeleri izle ve çıktıyı **JSON** formatında, kök anahtarı "products" olan tek bir nesne olarak döndür.
```

---

**End of Guide (v2 – 13 Jun 2025)**
