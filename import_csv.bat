@echo off
setlocal EnableExtensions

if "%~1"=="" (
    echo Usage: import_csv.bat "C:\path\to\csv-or-folder"
    pause
    exit /b 1
)

if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat
python -m crypto_tax_tool.csv_import_cli "%~1"
if errorlevel 1 (
    echo CSV import failed.
    pause
    exit /b 1
)

echo CSV import completed.
pause
