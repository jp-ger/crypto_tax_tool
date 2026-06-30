from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel, Field


class HistoricalPrice(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    asset: str
    quote_asset: str = "EUR"
    timestamp: datetime
    price: Decimal
    provider: str
    pair: str | None = None
