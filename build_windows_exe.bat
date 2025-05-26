@echo off
REM Build standalone Windows executable for Streamlit app
REM Requires pyinstaller to be installed: pip install pyinstaller

set SCRIPT=streamlit_app.py
set DATAFOLDER=data

pyinstaller --noconfirm --onefile --add-data "%DATAFOLDER%;%DATAFOLDER%" --hidden-import "streamlit.web.cli" %SCRIPT%

ECHO Build complete. Look in the dist folder for the EXE.
