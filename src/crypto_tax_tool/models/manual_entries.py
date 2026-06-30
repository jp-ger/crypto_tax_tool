from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel, Field


class ManualPriceEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    asset: str
    quote_asset: str = "EUR"
    timestamp: datetime
    price: Decimal
    reason: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ManualLotEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    asset: str
    acquired_at: datetime
    quantity: Decimal
    cost_basis_eur: Decimal
    reason: str
    source_reference: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ManualChangeLogEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    entity_type: str
    entity_id: str
    action: str
    reason: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
