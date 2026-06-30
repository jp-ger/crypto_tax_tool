# Windows Testing Guide

## 1. Pull the branch

```bat
git pull
git checkout feature/project-foundation
git pull
```

## 2. Build the application

Double-click:

```bat
build_windows.bat
```

or run it from PowerShell/CMD:

```bat
.\build_windows.bat
```

The script will:

- create `.venv`
- install dependencies
- run tests
- build the EXE

## 3. Start the EXE

```bat
.\dist\CryptoTaxTool.exe
```

## 4. Data location

The app stores local data according to the configured settings. Keep the generated SQLite database and report folders separate from the EXE.

Backups are created before sync and report generation under the app data backup directory.

## 5. First safe Binance test

Use a read-only Binance API key.

Start with a small period, for example one week, before syncing the full history.

## 6. If the build fails

Copy the last 30-50 lines from the command window and use them for troubleshooting.

Common causes:

- Python not added to PATH
- Python older than 3.11
- antivirus blocks PyInstaller output
- interrupted dependency installation
- no internet connection during dependency installation
