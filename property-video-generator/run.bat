@echo off
title AI Property Video Generator
echo.
echo ========================================
echo   AI Property Video Generator
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    pause
    exit /b 1
)

echo Installing / checking dependencies...
pip install -r requirements.txt -q

echo.
echo Choose mode:
echo   1. Web Interface (recommended)
echo   2. Command-line sample
echo.
set /p choice="Enter 1 or 2: "

if "%choice%"=="1" (
    echo.
    echo Starting web interface...
    echo Open the URL shown below in your browser.
    echo.
    streamlit run app.py
) else (
    echo.
    echo Running sample...
    python main.py --sample
    echo.
    echo Video saved in the output folder.
    pause
)
