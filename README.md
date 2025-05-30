# Smart_Price

Akıllı Fiyat Asistanı

## Installation

The required Python packages are listed in `pyproject.toml`. Install them together with this project using `pip`:

```bash
pip install .
```

`tkinter` must also be available. It is typically included with many Python distributions but may require a separate installation on some systems.

The tools attempt to locate the `tesseract` executable automatically using `shutil.which`. If `TESSDATA_PREFIX` is already defined it is respected, otherwise the location of the bundled language files is guessed from the executable path. When `tesseract` cannot be found a Windows default of `D:\Program Files\Tesseract-OCR` is used.

PDF files are parsed entirely through GPT‑4o Vision. Each page image is generated with **pdf2image** and sent to the model with a Turkish prompt. The response contains structured JSON for the rows.

### LLM assistance

When page images are sent to the LLM they include a detailed Turkish prompt
describing how to detect column headers such as *Ürün*, *Ürün Kodu* and *Price*
and how to return the rows as JSON with fields like *Malzeme_Kodu*, *Fiyat*,
*Açıklama*, *Adet*, *Birim*, *Para_Birimi*, *Marka* and *Kutu_Adedi*. Provide an
`OPENAI_API_KEY` environment variable or a `.env` file containing the key to
enable this step. Optionally set `OPENAI_MODEL` to override the default
`gpt-4o` model. The Vision API is queried with a temperature of `0`.

### Building a Windows executable

You can package the Streamlit interface into a single Windows executable using
PyInstaller. First install it with `pip install pyinstaller`.

Run the provided `build_windows_exe.bat` script from a Windows command
prompt:

```bat
build_windows_exe.bat
```

The script bundles everything inside the `data` directory so that any price
lists placed there (for example an initial `master_dataset.xlsx`) are available
once the executable is launched. The resulting binary will appear in the
`dist` folder.

### Price normalization

The `normalize_price` helper converts textual prices into numeric values. By
default it assumes European formatting (e.g. `1.234,56`). Pass
`style="en"` to handle English formatted numbers such as `1,234.56`.

### Code and description extraction

Product entries may contain material codes alongside descriptions in various formats. The parser recognises patterns such as `CODE / Description`, `Description / CODE`, `Description (CODE)` and `(CODE) Description` before falling back to a simple prefix-based split.


### CLI usage

Extract prices from files on the command line and save the merged result using the provided console script:

```bash
smart-price-parser data/list.xlsx another.pdf -o merged_prices.xlsx
```

The parser writes its results to `output/` by default. Set `OUTPUT_DIR` to
change this location or specify `OUTPUT_EXCEL`, `OUTPUT_DB` and `OUTPUT_LOG`
to override each individual path.

### Running the Streamlit interface

Launch the web UI locally with:

```bash
smart-price-app
```
Alternatively run the included launcher script from the repository root:
```bash
python run_app.py
```

The upload page now includes an **İşlem türü** radio button. Choose
**Güncelleme** to overwrite existing data for the same brand, year and
month. When this mode is used the matching rows are removed from the master
dataset and any old debug files for those sources are deleted before the new
records are saved.

From the interface you can upload Excel/PDF price lists and search the
resulting master dataset. When you save the merged data it writes both
`Master data base/master_dataset.xlsx` and `Master data base/master.db`
relative to the directory from which you launch the app. The success
message shows the full paths of these files and notes whether a GitHub
upload was attempted.

### Logging

Both the CLI and the Streamlit interface create a log file at
`config.LOG_PATH` (default `smart_price.log` in the project directory). This log
captures detailed processing messages and is created automatically each time the
tools run. Open this file with a text editor or use commands such as
`tail -f smart_price.log` to inspect the output when troubleshooting.

Verbose details such as the chosen LLM model, prompt length and the raw
response returned by the OpenAI API are logged automatically. Per page images
and JSON responses are written to the `LLM_Output_db` directory under a
subfolder matching the processed PDF name.

#### Debug information

The log records extra details to help trace each step:

- the name of the processed file
- a timestamp for every event
- page numbers for processed pages
- a snippet of the prompt sent to the LLM
- and the first items parsed from the response.
- per-page debug files stored under `LLM_Output_db/<PDF adı>` (set
  `SMART_PRICE_DEBUG_DIR` to override the location)
 - set `GITHUB_REPO` and `GITHUB_TOKEN` to automatically push each debug
   directory and the files under `Master data base/` (including
   `master_dataset.xlsx` and `master.db`) to the configured repository
   under their respective folders (optionally specify `GITHUB_BRANCH`).
   If these variables are not set the upload is skipped gracefully.

## Troubleshooting

If the vision stage fails to produce any items, the log records the model name
and an excerpt of the prompt. This can help diagnose why the extraction failed.

The prompt length and raw response are always logged to help troubleshoot
unexpected LLM behaviour.
