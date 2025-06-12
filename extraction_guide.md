# LLM PDF Price List Extraction \u2013 Unified Guide (v2, 13\u202fJun\u202f2025)

> **IMPORTANT**: Section\u00a00 applies to **every** prompt. Brand sections only add or override details.

---

## 0 \u00b7 GLOBAL OUTPUT CONTRACT  \(\u1f7e5\u00a0MUST FOLLOW\)

1. **Always produce JSON**. Your first instruction sentence MUST include the word **"JSON"**.
2. Wrap every result in a single root object with the key **`"products"`**:

   ```json
   {
     "products": [
       { \u2026one product object\u2026 }
     ]
   }
   ```

   Return an *array* even if there is only **one** product.
3. Fields for every product object *(leave blank when not available)*:

   * `Malzeme_Kodu`
   * `A\u00e7\u0131klama`
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
4. **Cleaning\u00a0& Validation**

   * Strip *all* whitespace in `Malzeme_Kodu` \(e.g. `"M X 4 5 8S"` \u2192 `"MX458S"`\).
   * Preserve decimal separators exactly as printed.
   * Do **not** invent values; leave unknown fields `""`.
   * The final JSON must pass `json.loads()` and satisfy the above schema.

---

## 1 \u00b7 UNIVERSAL SYNONYM MAP

| Canonical\u00a0Field   | Accept any of these header texts                                                                                                                           |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Malzeme\_Kodu** | \u00fcr\u00fcn kodu, urun kodu, malzeme kodu, malzeme, stok kodu, kod, tip, ref no, ref., \u00fcr\u00fcn ref, \u00fcr\u00fcn tip, product code, part no, item name, item no, item number |
| **Kisa\_Kod**     | kisa kod, short code, shortcode, k\u0131sa \u00fcr\u00fcn kodu                                                                                                            |
| **A\u00e7\u0131klama**      | description, \u00fcr\u00fcn a\u00e7\u0131klamas\u0131, a\u00e7\u0131klama, aciklama, \u00f6zellikler, detay, product name, explanation                                                             |
| **Fiyat**         | fiyat, birim fiyat, liste fiyat\u0131, price, unit price, list price, tutar                                                                                     |
| **Para\_Birimi**  | para birimi, currency                                                                                                                                      |
| **Ana\_Baslik**   | ana ba\u015fl\u0131k, ana baslik, ana\_baslik                                                                                                                        |
| **Alt\_Baslik**   | alt ba\u015fl\u0131k, alt baslik, alt\_baslik                                                                                                                        |

For any synonym **not** listed here, map it to the closest canonical field following the same logic.

---

## 2 \u00b7 GENERAL EXTRACTION RULES

1. **Do not drop rows**: extract every real product row appearing in a table.
2. Exclude pure header / sub-\u2011header / footnote / image rows.
3. `Ana_Baslik` & `Alt_Baslik` must be populated for every product, using nearest visual headers as defined per brand.
4. For tables split across pages, continue using the last valid headers until a new header appears.
5. When a price list contains multiple currencies, set the value found in the currency column; otherwise use the brand default.

---

## 3 \u00b7 BRAND\u2011SPECIFIC PROMPTS

Only the **differences** from Sections\u00a00\u20112 are listed below.

### 3.1 STEED

* Constants: `Marka = "STEED"`, `Kaynak_Dosya = "Steed Fiyat Listesi\u00a02025"`, `Record_Code = "STEED"`
* `Ana_Baslik`: every bold, large heading on the page.
  `Alt_Baslik`: always `""`.

### 3.2 ESMAKSAN

* Constants: `Marka = "ESMAKSAN"`, `Kaynak_Dosya = "ESMAKSAN\u00a02025\u00a0MART\u00a0F\u0130YAT\u00a0L\u0130STES\u0130.pdf"`, `Record_Code = "ESMAKSAN"`
* `Ana_Baslik`: topmost large heading per page.
  `Alt_Baslik`: title of each table block if present, else `""`.

### 3.3 MATRIX

* Constants: `Marka = "MATRIX"`, `Kaynak_Dosya = "MATRIX Fiyat Listesi\u00a010.03.25.pdf"`, `Record_Code = "MATRIX"`, `Para_Birimi = "EUR"`
* `Ana_Baslik`: page-header series name (e.g. `"320\u00a0Series"`).
* `Alt_Baslik`: table block title (e.g. `"Model\u00a0321\u00a0|\u00a03/2\u00a0|\u00a0NC\u00a0-\u00a0NO"`, `"OPTIONS"`, `"ACCESSORIES"`). Blank if none.

### 3.4 GAMAK

* Constants: `Marka = "GAMAK"`, `Kaynak_Dosya`: PDF file name, `Record_Code = "GAMAK"`, `Para_Birimi = "\u20ba"`
* Header hierarchy: largest page title \u279c `Ana_Baslik`; second-level bold header \u279c `Alt_Baslik`.

### 3.5 OMEGA MOTOR

* Constants: `Marka = "OMEGA MOTOR"`, `Kaynak_Dosya = "Omega Motor T\u00fcm Fiyat Listeleri\u00a0Mart\u00a02025.pdf"`, `Record_Code = "OMEGA"`, `Para_Birimi = "USD"`
* Supports optional `Alt_Baslik2` when an additional speed/material line exists directly under `Alt_Baslik`.

### 3.6 REKORSAN

* Constants: `Marka = "REKORSAN"`, `Kaynak_Dosya = "Rekorsan-Fiyat Listesi-27.01.2025.pdf"`, `Record_Code = "REKORSAN"`, `Para_Birimi = "\u20ba"`
* `Alt_Baslik` is **always** `""`.

---

## 4 \u00b7 DEFAULT / FALLBACK PROMPT

Use when the PDF filename does **not** match any brand section above.

1. Identify the two highest-level visual headings: first \u2192 `Ana_Baslik`; second \u2192 `Alt_Baslik` (may be `""`).
2. Detect currency symbol for `Para_Birimi`; default to `""` if none.
3. Leave `Marka`, `Record_Code`, and `Kaynak_Dosya` as `""`.
4. Follow Sections\u00a00\u20112 for all other rules.

---

## 5 \u00b7 RETURN STATEMENT TEMPLATE (insert verbatim at the end of every prompt)

```
A\u015fa\u011f\u0131daki y\u00f6nergeleri izle ve \u00e7\u0131kt\u0131y\u0131 **JSON** format\u0131nda, k\u00f6k anahtar\u0131 "products" olan tek bir nesne olarak d\u00f6nd\u00fcr.
```

---

**End of Guide (v2 \u2013 13\u202fJun\u202f2025)**
