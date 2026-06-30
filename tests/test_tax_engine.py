from datetime import UTC, datetime
from decimal import Decimal

from crypto_tax_tool.models.enums import TaxCategory, TradeSide, TransactionKind, TransactionSource
from crypto_tax_tool.models.transactions import NormalizedTransaction
from crypto_tax_tool.services.pricing import HistoricalPriceService, StaticPriceProvider
from crypto_tax_tool.services.tax_engine import TaxEngine


def _tx(**kwargs) -> NormalizedTransaction:
    defaults = dict(
        source=TransactionSource.BINANCE,
        source_id="test",
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        kind=TransactionKind.TRADE,
        tax_category=TaxCategory.PRIVATE_DISPOSAL,
        asset="BTC",
        quantity=Decimal("0"),
    )
    defaults.update(kwargs)
    return NormalizedTransaction(**defaults)


def test_tax_engine_creates_disposal_from_fifo_lot(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CRYPTO_TAX_DB_PATH", str(tmp_path / "test.sqlite3"))

    from crypto_tax_tool.database.sqlite_store import initialize_sqlite
    from crypto_tax_tool.settings import get_settings

    get_settings.cache_clear()
    initialize_sqlite()

    price_service = HistoricalPriceService(
        providers=[StaticPriceProvider({("BTC", "EUR"): Decimal("50000"), ("USDC", "EUR"): Decimal("1")})]
    )
    engine = TaxEngine(price_service)

    buy = _tx(
        source_id="buy1",
        timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        asset="BTC",
        quantity=Decimal("0.1"),
        quote_asset="USDC",
        quote_quantity=Decimal("3000"),
        side=TradeSide.BUY,
    )
    sell = _tx(
        source_id="sell1",
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        asset="USDC",
        quantity=Decimal("5000"),
        quote_asset="BTC",
        quote_quantity=Decimal("0.1"),
        side=TradeSide.SELL,
    )

    result = engine.calculate([buy, sell])

    assert len(result.disposals) == 1
    assert result.disposals[0].cost_basis_eur == Decimal("3000")
    assert result.disposals[0].proceeds_eur == Decimal("5000")
    assert result.disposals[0].gain_eur == Decimal("2000")
