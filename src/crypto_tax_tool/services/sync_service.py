from collections.abc import Callable
from datetime import datetime

from crypto_tax_tool.api.exchange_base import ExchangeClient
from crypto_tax_tool.database.sqlite_store import save_balance_snapshot, save_transactions, set_sync_state
from crypto_tax_tool.models.transactions import NormalizedTransaction
from crypto_tax_tool.services.backup_service import BackupService


class SyncResult:
    def __init__(self, loaded: int, inserted: int, balance_rows: int = 0, backup_path: str | None = None) -> None:
        self.loaded = loaded
        self.inserted = inserted
        self.balance_rows = balance_rows
        self.backup_path = backup_path


class SyncService:
    def __init__(self, exchange_client: ExchangeClient, progress_callback: Callable[[str], None] | None = None) -> None:
        self.exchange_client = exchange_client
        self.progress_callback = progress_callback

    def _log(self, message: str) -> None:
        if self.progress_callback:
            self.progress_callback(message)

    def sync(self, start: datetime, end: datetime) -> SyncResult:
        self._log("Creating database backup before sync...")
        backup = BackupService().create_backup("before_sync")
        if backup.path:
            self._log(f"Backup created: {backup.path}")
        else:
            self._log("No backup was created before sync.")

        self._log("Loading transactions from exchange...")
        rows: list[NormalizedTransaction] = self.exchange_client.sync_transactions(start=start, end=end)
        self._log(f"Loaded {len(rows)} transaction rows from exchange.")

        self._log("Saving transactions to local database...")
        inserted = save_transactions(rows)
        self._log(f"Saved transactions. New rows inserted: {inserted}.")

        balance_rows = 0
        if hasattr(self.exchange_client, "get_account_snapshot"):
            self._log("Loading current Binance account balance snapshot...")
            snapshot = self.exchange_client.get_account_snapshot()
            balance_rows = save_balance_snapshot(snapshot)
            set_sync_state("last_balance_snapshot", snapshot.timestamp.isoformat())
            self._log(f"Saved balance snapshot rows: {balance_rows}.")

        set_sync_state("last_sync_end", end.isoformat())
        self._log("Binance synchronization finished successfully.")
        return SyncResult(
            loaded=len(rows),
            inserted=inserted,
            balance_rows=balance_rows,
            backup_path=str(backup.path) if backup.path else None,
        )
