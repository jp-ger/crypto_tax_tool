@echo off
setlocal EnableExtensions EnableDelayedExpansion

title Crypto Tax Tool - Windows Setup and Build

echo ============================================================
echo Crypto Tax Tool - Windows Setup and EXE Build
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python was not found.
    echo Please install Python 3.11 or newer and enable "Add python.exe to PATH".
    pause
    exit /b 1
)

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 (
    echo ERROR: Python 3.11 or newer is required.
    python --version
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv --clear
    if errorlevel 1 (
        echo ERROR: Could not create virtual environment.
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Could not activate virtual environment.
    pause
    exit /b 1
)

echo Checking pip inside virtual environment...
python -m pip --version >nul 2>nul
if errorlevel 1 (
    echo pip is broken in .venv. Recreating virtual environment...
    deactivate >nul 2>nul
    rmdir /s /q .venv
    python -m venv .venv --clear
    if errorlevel 1 goto :error
    call .venv\Scripts\activate.bat
    if errorlevel 1 goto :error
    python -m ensurepip --upgrade
    if errorlevel 1 goto :error
)

echo Upgrading pip tooling...
python -m ensurepip --upgrade
if errorlevel 1 goto :error
python -m pip install --upgrade --force-reinstall pip setuptools wheel
if errorlevel 1 goto :error

echo Installing application, dev and build dependencies...
python -m pip install --no-cache-dir -e ".[dev,build]"
if errorlevel 1 goto :error

echo.
echo Running tests...
python -m pytest
if errorlevel 1 (
    echo.
    echo ERROR: Tests failed. EXE build stopped.
    pause
    exit /b 1
)

echo.
echo Building EXE with PyInstaller...
if not exist "dist" mkdir dist
python -m PyInstaller ^
    --name CryptoTaxTool ^
    --onefile ^
    --windowed ^
    --clean ^
    --paths src ^
    --collect-all PySide6 ^
    src\crypto_tax_tool\__main__.py
if errorlevel 1 goto :error

echo.
echo ============================================================
echo Build completed successfully.
echo EXE location:
echo %cd%\dist\CryptoTaxTool.exe
echo ============================================================
echo.
pause
exit /b 0

:error
echo.
echo ERROR: Setup or build failed.
pause
exit /b 1
