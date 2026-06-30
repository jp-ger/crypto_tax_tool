@echo off
setlocal EnableExtensions

title Crypto Tax Tool - Run from Source

if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment not found.
    echo Please run build_windows.bat first.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Could not activate virtual environment.
    pause
    exit /b 1
)

python -m crypto_tax_tool
if errorlevel 1 (
    echo.
    echo ERROR: Application exited with an error.
    pause
    exit /b 1
)
