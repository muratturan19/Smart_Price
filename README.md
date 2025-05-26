# Smart_Price

Akıllı Fiyat Asistanı

## Requirements

This project relies on a few Python packages:

- `pandas`
- `pdfplumber`

Make sure these are installed, for example using `pip install pandas pdfplumber`.

`tkinter` must also be available. It is typically included with many Python distributions but may require a separate installation on some systems.

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
