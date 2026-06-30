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
    def __init__(self, exchange_client: ExchangeClient) -> None:
        self.exchange_client = exchange_client

    def sync(self, start: datetime, end: datetime) -> SyncResult:
        backup = BackupService().create_backup("before_sync")
        rows: list[NormalizedTransaction] = self.exchange_client.sync_transactions(start=start, end=end)
        inserted = save_transactions(rows)
        balance_rows = 0
        if hasattr(self.exchange_client, "get_account_snapshot"):
            snapshot = self.exchange_client.get_account_snapshot()
            balance_rows = save_balance_snapshot(snapshot)
            set_sync_state("last_balance_snapshot", snapshot.timestamp.isoformat())
        set_sync_state("last_sync_end", end.isoformat())
        return SyncResult(
            loaded=len(rows),
            inserted=inserted,
            balance_rows=balance_rows,
            backup_path=str(backup.path) if backup.path else None,
        )
