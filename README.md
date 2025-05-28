# Smart_Price

Akıllı Fiyat Asistanı

## Installation

The required Python packages are listed in `pyproject.toml`. Install them together with this project using `pip`:

```bash
pip install .
```

`tkinter` must also be available. It is typically included with many Python distributions but may require a separate installation on some systems.

PDF files are processed in two stages. First the parser attempts to read text directly using **pdfplumber**. If no products are found the entire document is converted to images with `pdftoppm` and recognised by **Tesseract**. The resulting text is then interpreted by a language model.
Both `pdftoppm` from **Poppler** and **Tesseract** itself must therefore be installed. On Debian based
Linux systems install them with:

```bash
sudo apt-get install poppler-utils tesseract-ocr
```

Windows users can download the Poppler and Tesseract binaries and ensure that
`pdftoppm.exe` and `tesseract.exe` are available in the `PATH`. Both utilities
must be discoverable on your system PATH for the OCR phase to succeed.

### LLM assistance

After OCR the recognised text is sent to GPT-3.5 for interpretation. Provide an
`OPENAI_API_KEY` environment variable or a `.env` file containing the key to
enable this step. Optionally set `OPENAI_MODEL` to override the default
`gpt-3.5-turbo` model. The model is queried with a temperature of `0.2` and a
small delay is added between requests to respect API rate limits.

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

### Running the Streamlit interface

Launch the web UI locally with:

```bash
smart-price-app
```

From the interface you can upload Excel/PDF price lists and search the
resulting master dataset. The merged data is written to `master_dataset.xlsx`
in the directory from which you launch the app.

### Logging

Both the CLI and the Streamlit interface create a `smart_price.log` file in the
project directory (or whichever path is passed to `init_logging`). This log
captures detailed processing messages and is created automatically each time the
tools run. Open this file with a text editor or use commands such as
`tail -f smart_price.log` to inspect the output when troubleshooting.

## Troubleshooting

If the second stage (OCR followed by the language model) fails to produce any
items, the log records the model name and a short excerpt of the recognised text.
Look for entries
like:

```
no items parsed by gpt-3.5-turbo; OCR text excerpt: 'Example line from scan'
```

This can help diagnose why the extraction failed.
