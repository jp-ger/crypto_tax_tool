from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from crypto_tax_tool.models.enums import TaxCategory, TradeSide, TransactionKind, TransactionSource


class MoneyAmount(BaseModel):
    asset: str
    amount: Decimal


class NormalizedTransaction(BaseModel):
    """Exchange-independent transaction representation used by tax and report engines."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    source: TransactionSource = TransactionSource.BINANCE
    source_id: str
    timestamp: datetime
    kind: TransactionKind
    tax_category: TaxCategory = TaxCategory.UNKNOWN
    asset: str
    quantity: Decimal
    quote_asset: str | None = None
    quote_quantity: Decimal | None = None
    fee_asset: str | None = None
    fee_quantity: Decimal | None = None
    side: TradeSide | None = None
    product: str | None = None
    raw_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
