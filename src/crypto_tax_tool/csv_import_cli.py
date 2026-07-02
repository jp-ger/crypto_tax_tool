import argparse
from pathlib import Path

from crypto_tax_tool.services.binance_transaction_history_import_service import BinanceTransactionHistoryImportService


def main() -> None:
    parser = argparse.ArgumentParser(description="Import exchange CSV exports.")
    parser.add_argument("path", help="CSV file or folder containing CSV exports")
    args = parser.parse_args()
    result = BinanceTransactionHistoryImportService().import_path(Path(args.path))
    print(f"CSV import completed: files={result.files}, rows_seen={result.rows_seen}, normalized={result.rows_imported}, inserted={result.rows_inserted}, skipped={result.rows_skipped}")


if __name__ == "__main__":
    main()
