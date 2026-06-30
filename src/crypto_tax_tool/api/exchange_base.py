from abc import ABC, abstractmethod
from datetime import datetime

from crypto_tax_tool.models.transactions import NormalizedTransaction


class ExchangeClient(ABC):
    """Base interface for exchange importers."""

    @abstractmethod
    def test_connection(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def sync_transactions(self, start: datetime, end: datetime) -> list[NormalizedTransaction]:
        raise NotImplementedError
