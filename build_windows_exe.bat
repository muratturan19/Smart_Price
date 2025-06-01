@echo off
REM Build standalone Windows executable for Streamlit app
REM Requires pyinstaller to be installed: pip install pyinstaller

set SCRIPT=Price App\smart_price\streamlit_app.py
set DATAFOLDER=data
set LOGOFOLDER=logo

pyinstaller --noconfirm --onefile --add-data "%DATAFOLDER%;%DATAFOLDER%" --add-data "%LOGOFOLDER%;logo" --hidden-import "streamlit.web.cli" --collect-all streamlit "%SCRIPT%"

ECHO Build complete. Look in the dist folder for the EXE.
