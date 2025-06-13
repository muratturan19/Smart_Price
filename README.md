# Smart_Price

Akıllı Fiyat Asistanı

## Installation

The required Python packages are listed in `pyproject.toml`. Install them together with this project using `pip`:

```bash
pip install -e .
# or
pip install smart-price
```
This project uses explicit package mappings in `pyproject.toml`, so the
editable install works on Windows and other platforms.

Utilities live under `smart_price.utils`.

```python
from smart_price.utils.prompt_builder import get_prompt_for_file
```

`tkinter` must also be available. It is typically included with many Python distributions but may require a separate installation on some systems.

Smart_Price supports **Python 3.8** through **3.12**.

The Poppler utilities `pdftoppm.exe`, `pdftocairo.exe` and `pdfinfo.exe` are
also required for PDF processing. The repository only contains placeholder
files in the `poppler/bin` directory, so download the real executables and
replace the placeholders before running the tools.

### Poppler setup

Download Poppler for Windows (64-bit) and copy `pdftoppm.exe`,
`pdftocairo.exe` and `pdfinfo.exe` into `poppler/bin`.

PDFs are converted to images and parsed directly with the Vision+LLM pipeline.

### LLM assistance

When page images are sent to the LLM they include a detailed Turkish prompt
describing how to detect column headers such as *Ürün*, *Ürün Kodu* and *Price*
and how to return the rows as JSON with fields like *Malzeme_Kodu*, *Fiyat*,
*Açıklama*, *Adet*, *Birim*, *Para_Birimi*, *Marka* and *Kutu_Adedi*. Provide an
`OPENAI_API_KEY` environment variable or a `.env` file containing the key to
enable this step. Optionally set `OPENAI_MODEL` to override the default
`gpt-4o` model. Set `OPENAI_MAX_RETRIES` to update
`openai.api_requestor._DEFAULT_NUM_RETRIES` (defaults to `0`). The
request itself no longer passes a `max_retries` argument and the Vision
API is queried with a temperature of `0`.

### Agentic document extraction

Install the optional `agentic` extra (or install `agentic-doc` separately)
to try an alternative PDF pipeline:

```bash
pip install smart-price[agentic]
```

Set both `OPENAI_API_KEY` and `VISION_AGENT_API_KEY` in your `.env` file.
When uploading files in the interface choose **AgenticDE** under
**PDF extraction method** to activate this workflow. Both parsing pipelines
use the same prompt structure, so results should be comparable.

Example CLI usage:

```bash
smart-price-parser tests/samples/ESMAKSAN_2025_MART.pdf -o out.xlsx
```

The AgenticDE client automatically retries failed HTTP requests such as
rate limit responses (429) or temporary 502--504 errors.  Parallelism and
retry behaviour can be tuned by setting the following environment
variables in your `.env` file:

```bash
# Number of files processed in parallel
BATCH_SIZE=4
# Worker threads per file
MAX_WORKERS=2
# Retry attempts for intermittent failures
MAX_RETRIES=80
# Maximum wait time per retry in seconds
MAX_RETRY_WAIT_TIME=30
# Logging style for retries: log_msg, inline_block or none
RETRY_LOGGING_STYLE=log_msg
```

These values configure the internal `agentic_doc` Settings object.  The
optimal numbers depend on your API rate limit and document size. The same
`MAX_RETRIES` and `MAX_RETRY_WAIT_TIME` variables control how often the
fallback OCR+LLM parser re-attempts timed out requests.

``agentic_doc.parse`` now returns a list of ``ParsedDocument`` objects. The
tools use the first item in that list. When an extraction guide provides
page prompts for a PDF file these prompts are forwarded to
``agentic_doc.parse``.

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
once the executable is launched.  It also adds the `logo` folder to ensure
the images used by the interface are packaged together with the `.streamlit`
configuration folder.  The resulting binary will appear in the `dist` folder.
The Poppler binaries are bundled from the `poppler/bin` folder so the resulting
EXE runs without additional dependencies. Place the actual `pdftoppm.exe`,
`pdftocairo.exe` and `pdfinfo.exe` files there first. If you store these tools
elsewhere edit `POPPLERDIR` in
`build_windows_exe.bat` to point to the correct paths.  The batch file
collects all Streamlit resources so the executable launches without a
`PackageNotFoundError` for the `streamlit` distribution. The launcher script
sets `STREAMLIT_SERVER_PORT=8501` and `STREAMLIT_SERVER_HEADLESS=false` so the
browser opens automatically when the app is started from the generated EXE.

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
The resulting SQLite database contains `main_header` and `sub_header`
columns to store any detected section headings.

### Running the Streamlit interface

Launch the web UI locally with:

```bash
smart-price-app
```
Alternatively run the included launcher script from the repository root:
```bash
python run_app.py
```

The look and feel of the interface is defined in `.streamlit/config.toml`:

```toml
[theme]
primaryColor = "#002060"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"
```

Modify these values if you wish to adjust the colour scheme or font.

The floating logo displayed in the top right corner of both Streamlit
applications can also be customised.  Set ``LOGO_TOP`` and ``LOGO_RIGHT`` in
``config.json`` or as environment variables to control its position.  Adjust
``LOGO_OPACITY`` to change how transparent the overlay appears.  Use the
``tooltip`` argument of ``smart_price.ui_utils.logo_overlay`` to set a hover
hint or hyperlink.

The upload page now includes an **İşlem türü** radio button. Choose
**Güncelleme** to overwrite existing data for the same brand, year and
month. When this mode is used the matching rows are removed from the master
dataset and any old debug files for those sources are deleted before the new
records are saved.

From the interface you can upload Excel/PDF price lists and search the
resulting master dataset. When you save the merged data it writes both
`Master_data_base/master_dataset.xlsx` and `Master_data_base/master.db`
relative to the directory from which you launch the app. The success
message shows the full paths of these files and notes whether a GitHub
upload was attempted.

### Interface workflow

1. Click **"Dosyaları İşle"** after uploading your files.
2. Review the displayed dataframe to verify the extracted rows.
3. Click **"Master Veriyi Kaydet"** to write `master_dataset.xlsx` and
   `master.db` inside the `Master_data_base` folder. The same button
   also triggers the optional GitHub upload when credentials are
   configured.

### Logging

Both the CLI and the Streamlit interface create a log file at
`config.LOG_PATH` (default `smart_price.log` in the project directory). This log
captures detailed processing messages and is created automatically each time the
tools run. Open this file with a text editor or use commands such as
`tail -f smart_price.log` to inspect the output when troubleshooting.

Verbose details such as the chosen LLM model, prompt length and the raw
response returned by the OpenAI API are logged automatically. Per page images
are written to the `LLM_Output_db` directory while the JSON responses are saved
under `LLM_Text_db` (override with `SMART_PRICE_TEXT_DIR`). Each processed PDF
uses its own subfolder.

#### Debug information

The log records extra details to help trace each step:

- the name of the processed file
- a timestamp for every event
- page numbers for processed pages
- a snippet of the prompt sent to the LLM
- and the first items parsed from the response.
- per-page debug images stored under `LLM_Output_db/<PDF adı>` (set
  `SMART_PRICE_DEBUG_DIR` to override the location)
- per-page LLM responses stored under `LLM_Text_db/<PDF adı>` (set
  `SMART_PRICE_TEXT_DIR` to override the location)
Debug images can be downloaded directly from GitHub using a URL like
`https://raw.githubusercontent.com/<owner>/<repo>/main/LLM_Output_db/<PDF adı>/page_image_page_<NN>.jpg`.
These thumbnails are saved as progressive JPEG files with quality 80 for efficient storage.
Note that the `LLM_Output_db` folder sits at the repository root; **do not**
prefix the path with `Master_data_base`. Only the images in this folder are
uploaded automatically; text files remain in `LLM_Text_db`.
 - set `GITHUB_REPO` and `GITHUB_TOKEN` to automatically push each debug
   directory and the files under `Master_data_base/` (including
   `master_dataset.xlsx` and `master.db`) to the configured repository
   under their respective folders (optionally specify `GITHUB_BRANCH`).
   If these variables are not set the upload is skipped gracefully.
 - set `GITHUB_HTTP_TIMEOUT` to change the HTTP timeout for GitHub API
   requests in seconds (defaults to `30`).

### Resetting the dataset

Use the **Database Sıfırla** page in the Streamlit interface to remove all
local output and master files.  When GitHub credentials are configured the same
folders (`LLM_Output_db` and `Master_data_base`) are cleared from the
repository as well.

### Linting and tests

Run Ruff and the test suite:

```bash
ruff check .
pytest
```

The test suite expects packages such as `pandas`, `openai` and `pdf2image` to
be installed. Minimal stubs are provided when these are absent so most tests
still run, but a few checks will fail without the real dependencies.

Install the optional extras for full coverage:

```bash
pip install .[agentic]
```

## Troubleshooting

If the vision stage fails to produce any items, the log records the model name
and an excerpt of the prompt. This can help diagnose why the extraction failed.

The prompt length and raw response are always logged to help troubleshoot
unexpected LLM behaviour.

When the AgenticDE workflow is used, the log also notes the type of object
returned by ``agentic_doc.parse`` and dumps any ``page_summary`` entries. If no
rows are produced a warning records how many pages were processed. All these
messages include the source PDF name.
Set ``ADE_DEBUG=1`` to save each ``agentic_doc`` chunk under ``LLM_Output_db/<PDF name>``
and log its type and text. This is useful to inspect how table rows were
interpreted when header detection fails.
Errors raised by ``agentic_doc`` now log the HTTP status code, full response
text and exception details to help diagnose rate limit, authentication or
parsing issues.
