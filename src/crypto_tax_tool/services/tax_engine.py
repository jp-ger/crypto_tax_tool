from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from crypto_tax_tool.models.fifo_state import AssetLot, LotUsage
from crypto_tax_tool.models.transactions import NormalizedTransaction
from crypto_tax_tool.services.fee_service import FeeService
from crypto_tax_tool.services.fifo_engine import FifoEngine, InsufficientInventoryError
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
    disposed_at: datetime | None = None

    @property
    def cost_basis_eur(self) -> Decimal:
        return sum((match.cost_basis_eur for match in self.matches), Decimal("0"))

    @property
    def gain_eur(self) -> Decimal:
        return self.proceeds_eur - self.cost_basis_eur


@dataclass(frozen=True)
class IncomeResult:
    transaction_id: str
    asset: str
    quantity: Decimal
    income_eur: Decimal
    received_at: datetime
    product: str | None
    raw_type: str | None
    price_eur: Decimal
    price_provider: str
    price_pair: str | None


@dataclass(frozen=True)
class MissingInventoryIssue:
    transaction_id: str
    asset: str
    missing_quantity: Decimal
    disposed_quantity: Decimal
    proceeds_eur: Decimal
    disposed_at: datetime | None
    product: str | None
    raw_type: str | None
    message: str


@dataclass(frozen=True)
class TaxCalculationResult:
    disposals: list[DisposalResult]
    open_lots: list[AssetLot]
    income_events: list[IncomeResult] | None = None
    missing_inventory_issues: list[MissingInventoryIssue] | None = None

    @property
    def total_gain_eur(self) -> Decimal:
        return sum((item.gain_eur for item in self.disposals), Decimal("0"))

    @property
    def total_income_eur(self) -> Decimal:
        return sum((item.income_eur for item in self.income_events or []), Decimal("0"))


class TaxEngine:
    """Build FIFO lots, disposal results, and taxable income events."""

    def __init__(
        self,
        price_service: HistoricalPriceService,
        initial_lots: list[AssetLot] | None = None,
    ) -> None:
        self.price_service = price_service
        self.fee_service = FeeService(price_service)
        self.rule_classifier = GermanTaxRuleClassifier()
        self.fifo = FifoEngine()
        self._missing_inventory_issues: list[MissingInventoryIssue] = []
        for lot in sorted(initial_lots or [], key=lambda item: item.acquired_at):
            self.fifo.add_lot(lot)

    def calculate(self, transactions: list[NormalizedTransaction]) -> TaxCalculationResult:
        disposals: list[DisposalResult] = []
        income_events: list[IncomeResult] = []
        self._missing_inventory_issues = []
        for tx in sorted(transactions, key=lambda item: item.timestamp):
            rule = self.rule_classifier.classify(tx)
            if rule.action == "income_lot":
                income_events.append(self._add_income_lot(tx))
            elif rule.action == "acquisition_lot":
                self._add_buy_lot(tx)
            elif rule.action == "disposal":
                disposals.append(self._create_disposal(tx))

        return TaxCalculationResult(
            disposals=disposals,
            open_lots=list(self.fifo.open_lots()),
            income_events=income_events,
            missing_inventory_issues=self._missing_inventory_issues,
        )

    def _add_income_lot(self, tx: NormalizedTransaction) -> IncomeResult:
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
        return IncomeResult(
            transaction_id=tx.id,
            asset=tx.asset,
            quantity=tx.quantity,
            income_eur=cost_basis,
            received_at=tx.timestamp,
            product=tx.product,
            raw_type=tx.raw_type,
            price_eur=price.price,
            price_provider=price.provider,
            price_pair=price.pair,
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
        try:
            matches = self.fifo.use(disposed_asset, disposed_quantity, net_proceeds_eur, tx.timestamp)
        except InsufficientInventoryError as exc:
            matches = exc.matches
            self._missing_inventory_issues.append(
                MissingInventoryIssue(
                    transaction_id=tx.id,
                    asset=disposed_asset,
                    missing_quantity=exc.missing_quantity,
                    disposed_quantity=disposed_quantity,
                    proceeds_eur=net_proceeds_eur,
                    disposed_at=tx.timestamp,
                    product=tx.product,
                    raw_type=tx.raw_type,
                    message=str(exc),
                )
            )
        return DisposalResult(
            transaction_id=tx.id,
            asset=disposed_asset,
            quantity=disposed_quantity,
            proceeds_eur=net_proceeds_eur,
            matches=matches,
            fee_eur=fee_eur,
            disposed_at=tx.timestamp,
        )
