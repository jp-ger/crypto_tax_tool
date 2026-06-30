from datetime import UTC, datetime
from decimal import Decimal

from crypto_tax_tool.models.enums import TaxCategory, TradeSide, TransactionKind, TransactionSource
from crypto_tax_tool.models.transactions import NormalizedTransaction
from crypto_tax_tool.services.tax_rules import GermanTaxRuleClassifier


def _tx(**kwargs) -> NormalizedTransaction:
    defaults = dict(
        source=TransactionSource.BINANCE,
        source_id="test",
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        kind=TransactionKind.TRADE,
        tax_category=TaxCategory.UNKNOWN,
        asset="BTC",
        quantity=Decimal("0.1"),
    )
    defaults.update(kwargs)
    return NormalizedTransaction(**defaults)


def test_buy_is_acquisition_lot() -> None:
    result = GermanTaxRuleClassifier().classify(_tx(side=TradeSide.BUY))
    assert result.action == "acquisition_lot"
    assert result.category == TaxCategory.PRIVATE_DISPOSAL


def test_sell_is_disposal() -> None:
    result = GermanTaxRuleClassifier().classify(_tx(side=TradeSide.SELL))
    assert result.action == "disposal"
    assert result.category == TaxCategory.PRIVATE_DISPOSAL


def test_reward_is_income_lot() -> None:
    result = GermanTaxRuleClassifier().classify(
        _tx(kind=TransactionKind.REWARD, side=None, product="simple_earn_flexible")
    )
    assert result.action == "income_lot"
    assert result.category == TaxCategory.OTHER_INCOME


def test_deposit_is_transfer_only() -> None:
    result = GermanTaxRuleClassifier().classify(_tx(kind=TransactionKind.DEPOSIT, side=None))
    assert result.action == "transfer_only"
    assert result.category == TaxCategory.NON_TAXABLE_TRANSFER
