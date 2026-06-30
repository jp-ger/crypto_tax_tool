from datetime import UTC, datetime
from decimal import Decimal

from crypto_tax_tool.models.enums import TaxCategory, TradeSide, TransactionKind, TransactionSource
from crypto_tax_tool.models.fifo_state import AssetLot
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


def _price_service(tmp_path, monkeypatch) -> HistoricalPriceService:
    monkeypatch.setenv("CRYPTO_TAX_DB_PATH", str(tmp_path / "test.sqlite3"))

    from crypto_tax_tool.database.sqlite_store import initialize_sqlite
    from crypto_tax_tool.settings import get_settings

    get_settings.cache_clear()
    initialize_sqlite()

    return HistoricalPriceService(
        providers=[
            StaticPriceProvider(
                {
                    ("BTC", "EUR"): Decimal("50000"),
                    ("USDC", "EUR"): Decimal("1"),
                    ("BNB", "EUR"): Decimal("300"),
                }
            )
        ]
    )


def _engine(tmp_path, monkeypatch) -> TaxEngine:
    return TaxEngine(_price_service(tmp_path, monkeypatch))


def test_tax_engine_creates_disposal_from_fifo_lot(tmp_path, monkeypatch) -> None:
    engine = _engine(tmp_path, monkeypatch)

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


def test_initial_lot_can_cover_disposal(tmp_path, monkeypatch) -> None:
    initial_lot = AssetLot(
        id="manual_lot_1",
        asset="BTC",
        acquired_at=datetime(2021, 1, 1, tzinfo=UTC),
        quantity=Decimal("0.1"),
        remaining_quantity=Decimal("0.1"),
        cost_basis_eur=Decimal("1000"),
        source_transaction_id="manual",
    )
    engine = TaxEngine(_price_service(tmp_path, monkeypatch), initial_lots=[initial_lot])
    sell = _tx(
        source_id="sell_manual",
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        asset="USDC",
        quantity=Decimal("5000"),
        quote_asset="BTC",
        quote_quantity=Decimal("0.1"),
        side=TradeSide.SELL,
    )

    result = engine.calculate([sell])

    assert len(result.disposals) == 1
    assert result.disposals[0].cost_basis_eur == Decimal("1000")
    assert result.disposals[0].gain_eur == Decimal("4000")


def test_buy_fee_increases_cost_basis(tmp_path, monkeypatch) -> None:
    engine = _engine(tmp_path, monkeypatch)

    buy = _tx(
        source_id="buy_fee",
        timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        asset="BTC",
        quantity=Decimal("0.1"),
        quote_asset="USDC",
        quote_quantity=Decimal("3000"),
        fee_asset="USDC",
        fee_quantity=Decimal("5"),
        side=TradeSide.BUY,
    )

    result = engine.calculate([buy])

    assert result.open_lots[0].cost_basis_eur == Decimal("3005")


def test_sell_fee_reduces_proceeds(tmp_path, monkeypatch) -> None:
    engine = _engine(tmp_path, monkeypatch)

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
        source_id="sell_fee",
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        asset="USDC",
        quantity=Decimal("5000"),
        quote_asset="BTC",
        quote_quantity=Decimal("0.1"),
        fee_asset="USDC",
        fee_quantity=Decimal("10"),
        side=TradeSide.SELL,
    )

    result = engine.calculate([buy, sell])

    assert result.disposals[0].fee_eur == Decimal("10")
    assert result.disposals[0].proceeds_eur == Decimal("4990")
    assert result.disposals[0].gain_eur == Decimal("1990")
