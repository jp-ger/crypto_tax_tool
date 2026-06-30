from datetime import UTC, datetime
from decimal import Decimal

from crypto_tax_tool.models.enums import TaxCategory, TradeSide, TransactionKind, TransactionSource
from crypto_tax_tool.models.transactions import NormalizedTransaction
from crypto_tax_tool.services.reconciliation import InventoryCalculator, ReconciliationService


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


def test_inventory_calculates_buy_and_fee() -> None:
    tx = _tx(
        source_id="buy1",
        asset="BTC",
        quantity=Decimal("0.1"),
        quote_asset="USDC",
        quote_quantity=Decimal("5000"),
        fee_asset="USDC",
        fee_quantity=Decimal("1"),
        side=TradeSide.BUY,
    )

    balances = InventoryCalculator().calculate([tx])

    assert balances["BTC"] == Decimal("0.1")
    assert balances["USDC"] == Decimal("-5001")


def test_reconciliation_classifies_difference() -> None:
    report = ReconciliationService(tolerance=Decimal("0.01")).compare(
        expected={"BTC": Decimal("1")},
        actual={"BTC": Decimal("1.02")},
    )

    assert report.rows[0].status == "warning"
    assert not report.has_errors
