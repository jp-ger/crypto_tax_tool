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

set "APP_NAME=CryptoTaxTool"
set "TIMESTAMP=%DATE:~-4%%DATE:~3,2%%DATE:~0,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%"
set "TIMESTAMP=%TIMESTAMP: =0%"
set "BUILD_TMP=build_tmp_%TIMESTAMP%"
set "SPEC_TMP=spec_tmp_%TIMESTAMP%"

echo Closing running Crypto Tax Tool processes if present...
taskkill /F /IM CryptoTaxTool.exe >nul 2>nul
for /f "tokens=2" %%P in ('tasklist /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq Crypto Tax Tool*" /FO TABLE /NH 2^>nul') do taskkill /F /PID %%P >nul 2>nul
timeout /t 2 /nobreak >nul

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
echo Preparing clean build folders...
if not exist "dist" mkdir dist
if exist "%BUILD_TMP%" rmdir /s /q "%BUILD_TMP%"
if exist "%SPEC_TMP%" rmdir /s /q "%SPEC_TMP%"
mkdir "%BUILD_TMP%"
mkdir "%SPEC_TMP%"

echo Removing generated Python cache files...
for /d /r %%D in (__pycache__) do @if exist "%%D" rmdir /s /q "%%D" >nul 2>nul

echo.
echo Building EXE with PyInstaller...
python -m PyInstaller ^
    --name %APP_NAME% ^
    --onefile ^
    --windowed ^
    --clean ^
    --noconfirm ^
    --workpath "%BUILD_TMP%" ^
    --specpath "%SPEC_TMP%" ^
    --distpath dist ^
    --paths src ^
    --collect-all PySide6 ^
    src\crypto_tax_tool\__main__.py
if errorlevel 1 goto :error

echo Cleaning temporary build folders...
rmdir /s /q "%BUILD_TMP%" >nul 2>nul
rmdir /s /q "%SPEC_TMP%" >nul 2>nul

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
echo Build temp folder: %cd%\%BUILD_TMP%
echo Spec temp folder: %cd%\%SPEC_TMP%
echo.
echo If Windows still reports "Zugriff verweigert", close CryptoTaxTool.exe/python.exe in Task Manager
echo and run this file again.
pause
exit /b 1
