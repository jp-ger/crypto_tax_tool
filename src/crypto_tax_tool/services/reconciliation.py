from dataclasses import dataclass
from decimal import Decimal

from crypto_tax_tool.models.enums import TradeSide, TransactionKind
from crypto_tax_tool.models.transactions import NormalizedTransaction


@dataclass(frozen=True)
class AssetDifference:
    asset: str
    expected: Decimal
    actual: Decimal
    difference: Decimal
    status: str


@dataclass(frozen=True)
class ReconciliationReport:
    rows: list[AssetDifference]

    @property
    def has_errors(self) -> bool:
        return any(row.status == "error" for row in self.rows)


class InventoryCalculator:
    """Calculate expected asset balances from normalized transactions."""

    def calculate(self, transactions: list[NormalizedTransaction]) -> dict[str, Decimal]:
        balances: dict[str, Decimal] = {}
        for tx in sorted(transactions, key=lambda item: item.timestamp):
            if tx.kind in {TransactionKind.TRADE, TransactionKind.CONVERT}:
                self._apply_trade_like(balances, tx)
            elif tx.kind in {TransactionKind.REWARD, TransactionKind.INCOME, TransactionKind.DEPOSIT}:
                self._add(balances, tx.asset, tx.quantity)
            elif tx.kind == TransactionKind.WITHDRAWAL:
                self._subtract(balances, tx.asset, tx.quantity)
            if tx.fee_asset and tx.fee_quantity:
                self._subtract(balances, tx.fee_asset, tx.fee_quantity)
        return balances

    def _apply_trade_like(self, balances: dict[str, Decimal], tx: NormalizedTransaction) -> None:
        if tx.side == TradeSide.BUY:
            self._add(balances, tx.asset, tx.quantity)
            if tx.quote_asset and tx.quote_quantity:
                self._subtract(balances, tx.quote_asset, tx.quote_quantity)
        elif tx.side == TradeSide.SELL:
            self._subtract(balances, tx.quote_asset or tx.asset, tx.quote_quantity or tx.quantity)
            self._add(balances, tx.asset, tx.quantity)

    @staticmethod
    def _add(balances: dict[str, Decimal], asset: str, amount: Decimal) -> None:
        balances[asset] = balances.get(asset, Decimal("0")) + amount

    @staticmethod
    def _subtract(balances: dict[str, Decimal], asset: str, amount: Decimal) -> None:
        balances[asset] = balances.get(asset, Decimal("0")) - amount


class ReconciliationService:
    def __init__(self, tolerance: Decimal = Decimal("0.00000001")) -> None:
        self.tolerance = tolerance

    def compare(self, expected: dict[str, Decimal], actual: dict[str, Decimal]) -> ReconciliationReport:
        assets = sorted(set(expected) | set(actual))
        rows: list[AssetDifference] = []
        for asset in assets:
            expected_value = expected.get(asset, Decimal("0"))
            actual_value = actual.get(asset, Decimal("0"))
            difference = actual_value - expected_value
            status = self._classify(difference)
            rows.append(
                AssetDifference(
                    asset=asset,
                    expected=expected_value,
                    actual=actual_value,
                    difference=difference,
                    status=status,
                )
            )
        return ReconciliationReport(rows=rows)

    def _classify(self, difference: Decimal) -> str:
        if abs(difference) <= self.tolerance:
            return "ok"
        if abs(difference) <= self.tolerance * Decimal("1000"):
            return "warning"
        return "error"
