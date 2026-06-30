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


class DisposalMatch(BaseModel):
    disposal_transaction_id: str
    lot_id: str
    asset: str
    quantity: Decimal
    acquired_at: datetime
    disposed_at: datetime
    cost_basis_eur: Decimal
    proceeds_eur: Decimal

    @property
    def gain_eur(self) -> Decimal:
        return self.proceeds_eur - self.cost_basis_eur

    @property
    def holding_days(self) -> int:
        return (self.disposed_at.date() - self.acquired_at.date()).days
