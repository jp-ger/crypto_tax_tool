# Crypto Tax Tool V1 Freeze Checklist

## Local build gate

Run on Windows from the repository root:

```bat
build_windows.bat
```

The branch is ready for V1 freeze only if all steps finish successfully:

- Python 3.11+ detected
- Virtual environment created
- Dependencies installed
- Test suite passed
- `dist\CryptoTaxTool.exe` created

## Manual smoke test

1. Start `dist\CryptoTaxTool.exe`.
2. Confirm the GUI opens without errors.
3. Click `Check for updates`.
4. Click `Refresh local counts`.
5. Add one manual EUR price.
6. Add one manual FIFO lot.
7. Run `Create tax report` only after data exists.

## Live Binance test gate

Use a Binance API key with read-only permissions only.

Recommended first test:

1. Sync a small date range.
2. Check local counts.
3. Review validation warnings.
4. Create a report.
5. Open the generated Excel and CSV files.
6. Review the Audit CSV.

Then proceed with full account history.

## V1 freeze rule

After V1 freeze, do not add new features before the first full live validation is complete.
Allowed changes only:

- bug fixes
- import edge cases
- price lookup fixes
- validation fixes
- performance improvements
- documentation corrections

## Current V1 scope

Included:

- Binance sync foundation
- SQLite persistence
- FIFO tax engine
- German private disposal classification foundation
- manual prices
- manual FIFO lots
- validation assistant
- CSV report
- Excel report
- audit CSV
- update check
- Windows build script
- backups before sync/report

Not included in V1 freeze unless required by live-test bugs:

- automatic self-replacing updater
- PDF report
- portfolio dashboard
- multi-exchange support
- futures/margin specialization
- full installer
