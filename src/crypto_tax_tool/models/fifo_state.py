from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel, Field


class AssetLot(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    asset: str
    acquired_at: datetime
    quantity: Decimal
    remaining_quantity: Decimal
    cost_basis_eur: Decimal
    source_transaction_id: str


class LotUsage(BaseModel):
    lot_id: str
    asset: str
    acquired_at: datetime
    used_at: datetime
    quantity: Decimal
    cost_basis_eur: Decimal
    value_eur: Decimal

    @property
    def result_eur(self) -> Decimal:
        return self.value_eur - self.cost_basis_eur

    @property
    def holding_days(self) -> int:
        return (self.used_at.date() - self.acquired_at.date()).days
