from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel, Field

from crypto_tax_tool.models.enums import TransactionSource


class AssetBalance(BaseModel):
    asset: str
    free: Decimal
    locked: Decimal = Decimal("0")

    @property
    def total(self) -> Decimal:
        return self.free + self.locked


class BalanceSnapshot(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    source: TransactionSource = TransactionSource.BINANCE
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    balances: list[AssetBalance] = Field(default_factory=list)
