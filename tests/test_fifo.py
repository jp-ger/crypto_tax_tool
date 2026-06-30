from datetime import UTC, datetime
from decimal import Decimal

from crypto_tax_tool.models.enums import TaxCategory, TradeSide, TransactionKind, TransactionSource
from crypto_tax_tool.models.transactions import NormalizedTransaction
from crypto_tax_tool.services.fifo import FifoEngine
from crypto_tax_tool.services.pricing import HistoricalPriceService, StaticPriceProvider


def _trade(source_id: str, date: datetime, side: TradeSide, qty: str, quote_qty: str):
    return NormalizedTransaction(
        source=TransactionSource.BINANCE,
        source_id=source_id,
        timestamp=date,
        kind=TransactionKind.TRADE,
        tax_category=TaxCategory.PRIVATE_DISPOSAL,
        asset="BTC" if side == TradeSide.BUY else "EUR",
        quantity=Decimal(qty) if side == TradeSide.BUY else Decimal(quote_qty),
        quote_asset="EUR" if side == TradeSide.BUY else "BTC",
        quote_quantity=Decimal(quote_qty) if side == TradeSide.BUY else Decimal(qty),
        side=side,
        product="spot",
        raw_type="test",
    )


def test_fifo_matches_oldest_lot_first() -> None:
    price_service = HistoricalPriceService(
        providers=[StaticPriceProvider({("BTC", "EUR"): Decimal("10000")})]
    )
    engine = FifoEngine(price_service)
    rows = [
        _trade("buy1", datetime(2024, 1, 1, tzinfo=UTC), TradeSide.BUY, "1", "10000"),
        _trade("buy2", datetime(2024, 2, 1, tzinfo=UTC), TradeSide.BUY, "1", "20000"),
        _trade("sell1", datetime(2025, 1, 1, tzinfo=UTC), TradeSide.SELL, "1.5", "30000"),
    ]

    matches = engine.process(rows)

    assert len(matches) == 2
    assert matches[0].quantity == Decimal("1")
    assert matches[0].cost_basis_eur == Decimal("10000")
    assert matches[1].quantity == Decimal("0.5")
    assert matches[1].cost_basis_eur == Decimal("10000.0")
