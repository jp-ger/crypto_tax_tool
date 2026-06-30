from datetime import UTC, datetime
from decimal import Decimal

from crypto_tax_tool.database.sqlite_store import count_transactions, initialize_sqlite, save_transactions
from crypto_tax_tool.models.enums import TaxCategory, TradeSide, TransactionKind, TransactionSource
from crypto_tax_tool.models.transactions import NormalizedTransaction


def test_save_transactions(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setenv("CRYPTO_TAX_DB_PATH", str(db_path))

    from crypto_tax_tool.settings import get_settings

    get_settings.cache_clear()
    initialize_sqlite()

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
