from dataclasses import dataclass
from decimal import Decimal

from crypto_tax_tool.models.fifo_state import AssetLot, LotUsage
from crypto_tax_tool.models.transactions import NormalizedTransaction
from crypto_tax_tool.services.fee_service import FeeService
from crypto_tax_tool.services.fifo_engine import FifoEngine
from crypto_tax_tool.services.pricing import HistoricalPriceService
from crypto_tax_tool.services.tax_rules import GermanTaxRuleClassifier


@dataclass(frozen=True)
class DisposalResult:
    transaction_id: str
    asset: str
    quantity: Decimal
    proceeds_eur: Decimal
    matches: list[LotUsage]
    fee_eur: Decimal = Decimal("0")

    @property
    def cost_basis_eur(self) -> Decimal:
        return sum((match.cost_basis_eur for match in self.matches), Decimal("0"))

    @property
    def gain_eur(self) -> Decimal:
        return self.proceeds_eur - self.cost_basis_eur


@dataclass(frozen=True)
class TaxCalculationResult:
    disposals: list[DisposalResult]
    open_lots: list[AssetLot]

    @property
    def total_gain_eur(self) -> Decimal:
        return sum((item.gain_eur for item in self.disposals), Decimal("0"))


class TaxEngine:
    """Build FIFO lots and disposal results from normalized transactions."""

    def __init__(
        self,
        price_service: HistoricalPriceService,
        initial_lots: list[AssetLot] | None = None,
    ) -> None:
        self.price_service = price_service
        self.fee_service = FeeService(price_service)
        self.rule_classifier = GermanTaxRuleClassifier()
        self.fifo = FifoEngine()
        for lot in sorted(initial_lots or [], key=lambda item: item.acquired_at):
            self.fifo.add_lot(lot)

    def calculate(self, transactions: list[NormalizedTransaction]) -> TaxCalculationResult:
        disposals: list[DisposalResult] = []
        for tx in sorted(transactions, key=lambda item: item.timestamp):
            rule = self.rule_classifier.classify(tx)
            if rule.action == "income_lot":
                self._add_income_lot(tx)
            elif rule.action == "acquisition_lot":
                self._add_buy_lot(tx)
            elif rule.action == "disposal":
                disposals.append(self._create_disposal(tx))

        return TaxCalculationResult(disposals=disposals, open_lots=list(self.fifo.open_lots()))

    def _add_income_lot(self, tx: NormalizedTransaction) -> None:
        price = self.price_service.get_price(tx.asset, "EUR", tx.timestamp)
        cost_basis = tx.quantity * price.price
        self.fifo.add_lot(
            AssetLot(
                asset=tx.asset,
                acquired_at=tx.timestamp,
                quantity=tx.quantity,
                remaining_quantity=tx.quantity,
                cost_basis_eur=cost_basis,
                source_transaction_id=tx.id,
            )
        )

    def _add_buy_lot(self, tx: NormalizedTransaction) -> None:
        if tx.quote_asset == "EUR" and tx.quote_quantity is not None:
            cost_basis = tx.quote_quantity
        elif tx.quote_asset and tx.quote_quantity is not None:
            price = self.price_service.get_price(tx.quote_asset, "EUR", tx.timestamp)
            cost_basis = tx.quote_quantity * price.price
        else:
            price = self.price_service.get_price(tx.asset, "EUR", tx.timestamp)
            cost_basis = tx.quantity * price.price
        cost_basis += self.fee_service.fee_value_eur(tx)
        self.fifo.add_lot(
            AssetLot(
                asset=tx.asset,
                acquired_at=tx.timestamp,
                quantity=tx.quantity,
                remaining_quantity=tx.quantity,
                cost_basis_eur=cost_basis,
                source_transaction_id=tx.id,
            )
        )

    def _create_disposal(self, tx: NormalizedTransaction) -> DisposalResult:
        disposed_asset = tx.quote_asset or tx.asset
        disposed_quantity = tx.quote_quantity or tx.quantity
        if tx.asset == "EUR":
            gross_proceeds_eur = tx.quantity
        else:
            price = self.price_service.get_price(tx.asset, "EUR", tx.timestamp)
            gross_proceeds_eur = tx.quantity * price.price
        fee_eur = self.fee_service.fee_value_eur(tx)
        net_proceeds_eur = gross_proceeds_eur - fee_eur
        matches = self.fifo.use(disposed_asset, disposed_quantity, net_proceeds_eur, tx.timestamp)
        return DisposalResult(
            transaction_id=tx.id,
            asset=disposed_asset,
            quantity=disposed_quantity,
            proceeds_eur=net_proceeds_eur,
            matches=matches,
            fee_eur=fee_eur,
        )
