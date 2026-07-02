import csv
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from crypto_tax_tool.database.sqlite_store import save_transactions
from crypto_tax_tool.models.enums import TaxCategory, TransactionKind, TransactionSource
from crypto_tax_tool.models.transactions import NormalizedTransaction


@dataclass(frozen=True)
class BinanceTransactionHistoryImportResult:
    files: int
    rows_seen: int
    rows_imported: int
    rows_inserted: int
    rows_skipped: int


class BinanceTransactionHistoryImportService:
    """Import Binance Transaction History CSV exports as a fallback data source.

    Binance API coverage differs by account, region and product. Transaction History
    CSV exports often contain Simple Earn subscriptions, redemptions and interest even
    when the Simple Earn API endpoint returns HTTP 400.
    """

    SUPPORTED_SUFFIXES = {".csv"}

    def import_path(self, path: Path) -> BinanceTransactionHistoryImportResult:
        files = self._find_csv_files(path)
        total_seen = 0
        total_imported = 0
        total_inserted = 0
        total_skipped = 0

        for file_path in files:
            rows, seen, skipped = self._read_file(file_path)
            inserted = save_transactions(rows)
            total_seen += seen
            total_imported += len(rows)
            total_inserted += inserted
            total_skipped += skipped

        return BinanceTransactionHistoryImportResult(
            files=len(files),
            rows_seen=total_seen,
            rows_imported=total_imported,
            rows_inserted=total_inserted,
            rows_skipped=total_skipped,
        )

    def _find_csv_files(self, path: Path) -> list[Path]:
        if path.is_file() and path.suffix.lower() in self.SUPPORTED_SUFFIXES:
            return [path]
        if path.is_dir():
            return sorted(item for item in path.rglob("*.csv") if item.is_file())
        return []

    def _read_file(self, file_path: Path) -> tuple[list[NormalizedTransaction], int, int]:
        rows: list[NormalizedTransaction] = []
        seen = 0
        skipped = 0
        with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row_index, raw_row in enumerate(reader, start=2):
                seen += 1
                normalized = self._normalize_row(raw_row, file_path=file_path, row_index=row_index)
                if normalized is None:
                    skipped += 1
                    continue
                rows.append(normalized)
        return rows, seen, skipped

    def _normalize_row(
        self,
        row: dict[str, str | None],
        file_path: Path,
        row_index: int,
    ) -> NormalizedTransaction | None:
        clean = {self._norm_key(key): (value or "").strip() for key, value in row.items() if key}

        timestamp_raw = self._first(clean, "utc_time", "utctime", "time", "date", "timestamp")
        operation = self._first(clean, "operation", "type", "transaction_type", "tx_type")
        asset = self._first(clean, "coin", "asset", "currency", "token")
        amount_raw = self._first(clean, "change", "amount", "quantity", "qty")

        if not timestamp_raw or not operation or not asset or not amount_raw:
            return None

        try:
            timestamp = self._parse_timestamp(timestamp_raw)
            amount = Decimal(amount_raw.replace(",", ""))
        except (ValueError, InvalidOperation):
            return None

        if amount == 0:
            return None

        kind, tax_category = self._classify(operation=operation, amount=amount)
        source_id = self._source_id(file_path=file_path, row_index=row_index, row=row)

        return NormalizedTransaction(
            source=TransactionSource.BINANCE,
            source_id=f"transaction_history:{source_id}",
            timestamp=timestamp,
            kind=kind,
            tax_category=tax_category,
            asset=asset.upper(),
            quantity=abs(amount),
            product="transaction_history",
            raw_type=operation,
            metadata={
                "import_file": file_path.name,
                "row_index": row_index,
                "operation": operation,
                "signed_change": str(amount),
                "raw": dict(row),
            },
        )

    def _classify(self, operation: str, amount: Decimal) -> tuple[TransactionKind, TaxCategory]:
        op = operation.lower()
        if any(term in op for term in ["interest", "reward", "cashback", "commission rebate", "distribution"]):
            return TransactionKind.REWARD, TaxCategory.OTHER_INCOME
        if "deposit" in op:
            return TransactionKind.DEPOSIT, TaxCategory.NON_TAXABLE_TRANSFER
        if "withdraw" in op:
            return TransactionKind.WITHDRAWAL, TaxCategory.NON_TAXABLE_TRANSFER
        if any(term in op for term in ["subscription", "redemption", "transfer", "simple earn", "staking"]):
            return TransactionKind.ADJUSTMENT, TaxCategory.NON_TAXABLE_TRANSFER
        if any(term in op for term in ["buy", "sell", "convert", "trade"]):
            return TransactionKind.CONVERT, TaxCategory.PRIVATE_DISPOSAL
        return TransactionKind.INCOME if amount > 0 else TransactionKind.ADJUSTMENT, TaxCategory.UNKNOWN

    def _parse_timestamp(self, value: str) -> datetime:
        normalized = value.strip().replace(" UTC", "").replace("Z", "+00:00")
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y/%m/%d %H:%M:%S",
            "%d.%m.%Y %H:%M:%S",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(normalized, fmt).replace(tzinfo=UTC)
            except ValueError:
                pass
        parsed = datetime.fromisoformat(normalized)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

    def _source_id(self, file_path: Path, row_index: int, row: dict[str, str | None]) -> str:
        payload = "|".join(f"{key}={value}" for key, value in sorted(row.items()))
        digest = hashlib.sha256(f"{file_path.name}|{row_index}|{payload}".encode("utf-8")).hexdigest()
        return digest[:32]

    def _first(self, row: dict[str, str], *keys: str) -> str:
        for key in keys:
            value = row.get(key, "")
            if value:
                return value
        return ""

    def _norm_key(self, key: str) -> str:
        return key.strip().lower().replace(" ", "_").replace("-", "_")
