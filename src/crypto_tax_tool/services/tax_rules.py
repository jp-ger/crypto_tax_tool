from dataclasses import dataclass

from crypto_tax_tool.models.enums import TaxCategory, TradeSide, TransactionKind
from crypto_tax_tool.models.transactions import NormalizedTransaction


@dataclass(frozen=True)
class TaxRuleResult:
    transaction_id: str
    category: TaxCategory
    action: str
    description: str


class GermanTaxRuleClassifier:
    """Preliminary rule classifier for German private crypto tax documentation.

    This is not tax advice. The goal is to keep the treatment explicit and auditable.
    """

    def classify(self, tx: NormalizedTransaction) -> TaxRuleResult:
        if tx.kind in {TransactionKind.TRADE, TransactionKind.CONVERT}:
            return self._classify_trade_like(tx)
        if tx.kind in {TransactionKind.REWARD, TransactionKind.INCOME}:
            return TaxRuleResult(
                tx.id,
                TaxCategory.OTHER_INCOME,
                "income_lot",
                "Reward/income inflow; create lot with EUR value at inflow timestamp.",
            )
        if tx.kind in {TransactionKind.DEPOSIT, TransactionKind.WITHDRAWAL}:
            return TaxRuleResult(
                tx.id,
                TaxCategory.NON_TAXABLE_TRANSFER,
                "transfer_only",
                "Transfer without disposal by default; used for balance plausibility.",
            )
        return TaxRuleResult(tx.id, TaxCategory.UNKNOWN, "ignore", "Unknown transaction treatment.")

    def _classify_trade_like(self, tx: NormalizedTransaction) -> TaxRuleResult:
        if tx.side == TradeSide.BUY:
            return TaxRuleResult(
                tx.id,
                TaxCategory.PRIVATE_DISPOSAL,
                "acquisition_lot",
                "Acquisition of crypto asset; create FIFO lot including acquisition fees.",
            )
        if tx.side == TradeSide.SELL:
            return TaxRuleResult(
                tx.id,
                TaxCategory.PRIVATE_DISPOSAL,
                "disposal",
                "Disposal of crypto asset; calculate FIFO gain/loss and holding period.",
            )
        return TaxRuleResult(tx.id, TaxCategory.UNKNOWN, "review", "Trade-like record without side.")
