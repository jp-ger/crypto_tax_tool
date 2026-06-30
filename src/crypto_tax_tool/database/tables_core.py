from datetime import datetime

from sqlalchemy import DateTime, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from crypto_tax_tool.database.connection import Base


class TransactionRow(Base):
    __tablename__ = "tx_rows"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_tx_source_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    source_id: Mapped[str] = mapped_column(String(255), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    asset: Mapped[str] = mapped_column(String(32), index=True)
    qty: Mapped[float] = mapped_column(Numeric(38, 18))
    quote_asset: Mapped[str | None] = mapped_column(String(32), nullable=True)
    quote_qty: Mapped[float | None] = mapped_column(Numeric(38, 18), nullable=True)
    fee_asset: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fee_qty: Mapped[float | None] = mapped_column(Numeric(38, 18), nullable=True)
    side: Mapped[str | None] = mapped_column(String(16), nullable=True)
    product: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    extra: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
