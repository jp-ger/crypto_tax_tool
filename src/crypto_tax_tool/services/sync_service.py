from datetime import datetime

from crypto_tax_tool.api.exchange_base import ExchangeClient
from crypto_tax_tool.database.sqlite_store import save_transactions, set_sync_state
from crypto_tax_tool.models.transactions import NormalizedTransaction


class SyncResult:
    def __init__(self, loaded: int, inserted: int) -> None:
        self.loaded = loaded
        self.inserted = inserted


class SyncService:
    def __init__(self, exchange_client: ExchangeClient) -> None:
        self.exchange_client = exchange_client

    def sync(self, start: datetime, end: datetime) -> SyncResult:
        rows: list[NormalizedTransaction] = self.exchange_client.sync_transactions(start=start, end=end)
        inserted = save_transactions(rows)
        set_sync_state("last_sync_end", end.isoformat())
        return SyncResult(loaded=len(rows), inserted=inserted)
