from datetime import datetime

from crypto_tax_tool.api.exchange_base import ExchangeClient
from crypto_tax_tool.models.transactions import NormalizedTransaction


class SyncService:
    def __init__(self, exchange_client: ExchangeClient) -> None:
        self.exchange_client = exchange_client

    def sync(self, start: datetime, end: datetime) -> list[NormalizedTransaction]:
        return self.exchange_client.sync_transactions(start=start, end=end)
