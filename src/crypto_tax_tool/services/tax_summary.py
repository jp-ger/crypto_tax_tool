from dataclasses import dataclass
from decimal import Decimal

from crypto_tax_tool.services.tax_engine import DisposalResult, IncomeResult, TaxCalculationResult


@dataclass(frozen=True)
class DisposalSummaryRow:
    transaction_id: str
    asset: str
    quantity: Decimal
    proceeds_eur: Decimal
    cost_basis_eur: Decimal
    gain_eur: Decimal
    holding_days_min: int
    holding_days_max: int
    classification: str


@dataclass(frozen=True)
class IncomeSummaryRow:
    transaction_id: str
    asset: str
    quantity: Decimal
    income_eur: Decimal
    received_at: str
    product: str | None
    raw_type: str | None
    price_eur: Decimal
    price_provider: str
    price_pair: str | None


@dataclass(frozen=True)
class TaxSummary:
    rows: list[DisposalSummaryRow]
    taxable_gain_eur: Decimal
    long_held_gain_eur: Decimal
    total_gain_eur: Decimal
    income_rows: list[IncomeSummaryRow]
    taxable_income_eur: Decimal
    total_taxable_eur: Decimal


class TaxSummaryService:
    def build_summary(self, result: TaxCalculationResult) -> TaxSummary:
        rows: list[DisposalSummaryRow] = []
        income_rows: list[IncomeSummaryRow] = []
        taxable_gain = Decimal("0")
        long_held_gain = Decimal("0")
        taxable_income = Decimal("0")

        for disposal in result.disposals:
            row = self._build_row(disposal)
            rows.append(row)
            if row.classification == "long_held":
                long_held_gain += row.gain_eur
            else:
                taxable_gain += row.gain_eur

        for income in result.income_events or []:
            income_row = self._build_income_row(income)
            income_rows.append(income_row)
            taxable_income += income_row.income_eur

        return TaxSummary(
            rows=rows,
            taxable_gain_eur=taxable_gain,
            long_held_gain_eur=long_held_gain,
            total_gain_eur=taxable_gain + long_held_gain,
            income_rows=income_rows,
            taxable_income_eur=taxable_income,
            total_taxable_eur=taxable_gain + taxable_income,
        )

    def _build_row(self, disposal: DisposalResult) -> DisposalSummaryRow:
        if disposal.matches:
            holding_days = [match.holding_days for match in disposal.matches]
            min_days = min(holding_days)
            max_days = max(holding_days)
        else:
            min_days = 0
            max_days = 0

        classification = "long_held" if min_days > 365 else "short_held"

        return DisposalSummaryRow(
            transaction_id=disposal.transaction_id,
            asset=disposal.asset,
            quantity=disposal.quantity,
            proceeds_eur=disposal.proceeds_eur,
            cost_basis_eur=disposal.cost_basis_eur,
            gain_eur=disposal.gain_eur,
            holding_days_min=min_days,
            holding_days_max=max_days,
            classification=classification,
        )

    def _build_income_row(self, income: IncomeResult) -> IncomeSummaryRow:
        return IncomeSummaryRow(
            transaction_id=income.transaction_id,
            asset=income.asset,
            quantity=income.quantity,
            income_eur=income.income_eur,
            received_at=income.received_at.isoformat(),
            product=income.product,
            raw_type=income.raw_type,
            price_eur=income.price_eur,
            price_provider=income.price_provider,
            price_pair=income.price_pair,
        )
