# Smart_Price

Akıllı Fiyat Asistanı

## Installation

The required Python packages are listed in `pyproject.toml`. Install them together with this project using `pip`:

```bash
pip install .
```

`tkinter` must also be available. It is typically included with many Python distributions but may require a separate installation on some systems.

PDF files are processed in two stages. First the parser attempts to read text directly using **pdfplumber**. If no products are found each page image is generated with **pdf2image** and sent directly to GPT‑4o Vision with a Turkish prompt. The model returns structured JSON describing the rows.

### LLM assistance

When page images are sent to the LLM they are accompanied by the Turkish prompt
"Malzeme Kodu, Açıklama, Fiyat, Birim ve Kutu Adedi". Provide an
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

### Running the Streamlit interface

Launch the web UI locally with:

```bash
smart-price-app
```
Alternatively run the included launcher script from the repository root:
```bash
python run_app.py
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

Set the environment variable `SMART_PRICE_DEBUG=1` (or pass
`level=logging.DEBUG` when calling `init_logging`) to enable verbose debug
information. When active the log includes the chosen LLM model, the constructed
prompt length and the raw response returned by the OpenAI API. Per-page images
and JSON responses are saved to a folder.

#### Debug information

When debug mode is enabled the log also records extra details to help trace each
step:

- the name of the processed file
- a timestamp for every event
- page numbers for processed pages
- a snippet of the prompt sent to the LLM
- and the first items parsed from the response.
- per-page debug files stored under `output_debug` (set
  `SMART_PRICE_DEBUG_DIR` to change the folder)

## Troubleshooting

If the vision stage fails to produce any items, the log records the model name
and an excerpt of the prompt. This can help diagnose why the extraction failed.

When debug logging is enabled the prompt length and raw response are also logged
to help troubleshoot unexpected LLM behaviour.
