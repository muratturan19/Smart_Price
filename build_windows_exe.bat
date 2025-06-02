@echo off
REM Build standalone Windows executable for Streamlit app
REM Requires pyinstaller to be installed: pip install pyinstaller

REM Entry script that launches Streamlit using stcli
set SCRIPT=run_app.py
set DATAFOLDER=data
set LOGOFOLDER=logo
set PRICEAPP=Price App
set STREAMLITCFG=.streamlit
set POPLPLERDIR=poppler\bin

pyinstaller --noconfirm --onefile ^
    --add-data "%DATAFOLDER%;%DATAFOLDER%" ^
    --add-data "%LOGOFOLDER%;logo" ^
    --add-data "%PRICEAPP%;Price App" ^
    --add-data "%STREAMLITCFG%;.streamlit" ^
    --add-binary "%POPLPLERDIR%\*;poppler\bin" ^
    --hidden-import "streamlit.web.cli" --collect-all streamlit "%SCRIPT%"

ECHO Build complete. Look in the dist folder for the EXE.
