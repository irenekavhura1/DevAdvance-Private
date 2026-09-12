@echo off
setlocal

rem Always run from the folder this script lives in, so the venv, app.py,
rem and requirements.txt are found no matter where this .bat is launched from.
cd /d "%~dp0"

set PYTHON=venv\Scripts\python.exe

if not exist "%PYTHON%" (
    echo No virtual environment found in this folder yet - creating one...
    where python >nul 2>nul
    if errorlevel 1 (
        echo.
        echo Python was not found on your PATH. Install it from https://python.org
        echo and make sure "Add python.exe to PATH" is checked during setup, then
        echo run this script again.
        echo.
        pause
        exit /b 1
    )
    python -m venv venv
)

echo Installing/updating required packages (streamlit, pandas, plotly, openpyxl)...
"%PYTHON%" -m pip install --upgrade pip >nul 2>nul
"%PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Package install hit a problem. If the app already worked before,
    echo it may still run fine below using what's already installed.
)

echo.
echo Starting the Navachab Development Unit Cost Analyzer...
echo Your browser should open automatically at http://localhost:8501
echo Leave this window open while you use the app - close it, or press Ctrl+C, to stop.
echo.
"%PYTHON%" -m streamlit run app.py

echo.
echo The app has stopped.
pause
