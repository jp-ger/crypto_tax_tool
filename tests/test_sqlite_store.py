from datetime import UTC, datetime
from decimal import Decimal

from crypto_tax_tool.database.sqlite_store import (
    count_balance_rows,
    count_prices,
    count_transactions,
    get_cached_price,
    initialize_sqlite,
    save_balance_snapshot,
    save_price,
    save_transactions,
)
from crypto_tax_tool.models.balances import AssetBalance, BalanceSnapshot
from crypto_tax_tool.models.enums import TaxCategory, TradeSide, TransactionKind, TransactionSource
from crypto_tax_tool.models.prices import HistoricalPrice
from crypto_tax_tool.models.transactions import NormalizedTransaction


def _prepare_db(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setenv("CRYPTO_TAX_DB_PATH", str(db_path))

    from crypto_tax_tool.settings import get_settings

    get_settings.cache_clear()
    initialize_sqlite()


def test_save_transactions(tmp_path, monkeypatch) -> None:
    _prepare_db(tmp_path, monkeypatch)

    tx = NormalizedTransaction(
        source=TransactionSource.BINANCE,
        source_id="spot:BTCUSDC:1",
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        kind=TransactionKind.TRADE,
        tax_category=TaxCategory.PRIVATE_DISPOSAL,
        asset="BTC",
        quantity=Decimal("0.1"),
        quote_asset="USDC",
        quote_quantity=Decimal("5000"),
        fee_asset="USDC",
        fee_quantity=Decimal("1"),
        side=TradeSide.BUY,
        product="spot",
        raw_type="myTrades",
    )

    assert save_transactions([tx]) == 1
    assert save_transactions([tx]) == 0
    assert count_transactions() == 1


def test_save_balance_snapshot(tmp_path, monkeypatch) -> None:
    _prepare_db(tmp_path, monkeypatch)

    snapshot = BalanceSnapshot(
        source=TransactionSource.BINANCE,
        balances=[
            AssetBalance(asset="BTC", free=Decimal("0.1"), locked=Decimal("0")),
            AssetBalance(asset="USDC", free=Decimal("100"), locked=Decimal("5")),
        ],
    )

    assert save_balance_snapshot(snapshot) == 2
    assert count_balance_rows() == 2


def test_save_and_read_price(tmp_path, monkeypatch) -> None:
    _prepare_db(tmp_path, monkeypatch)
    timestamp = datetime(2025, 1, 1, tzinfo=UTC)
    price = HistoricalPrice(
        asset="BTC",
        quote_asset="EUR",
        timestamp=timestamp,
        price=Decimal("90000"),
        provider="test",
        pair="BTCEUR",
    )

    assert save_price(price) is True
    assert save_price(price) is False
    assert count_prices() == 1
    cached = get_cached_price("BTC", "EUR", timestamp)
    assert cached is not None
    assert cached.price == Decimal("90000")
