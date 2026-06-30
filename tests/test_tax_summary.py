from datetime import UTC, datetime
from decimal import Decimal

from crypto_tax_tool.models.fifo_state import LotUsage
from crypto_tax_tool.services.tax_engine import DisposalResult, TaxCalculationResult
from crypto_tax_tool.services.tax_summary import TaxSummaryService


def test_tax_summary_splits_short_and_long_held_results() -> None:
    short_disposal = DisposalResult(
        transaction_id="sell_short",
        asset="BTC",
        quantity=Decimal("0.1"),
        proceeds_eur=Decimal("5000"),
        matches=[
            LotUsage(
                lot_id="lot1",
                asset="BTC",
                acquired_at=datetime(2025, 1, 1, tzinfo=UTC),
                used_at=datetime(2025, 6, 1, tzinfo=UTC),
                quantity=Decimal("0.1"),
                cost_basis_eur=Decimal("3000"),
                value_eur=Decimal("5000"),
            )
        ],
    )
    long_disposal = DisposalResult(
        transaction_id="sell_long",
        asset="ETH",
        quantity=Decimal("1"),
        proceeds_eur=Decimal("2000"),
        matches=[
            LotUsage(
                lot_id="lot2",
                asset="ETH",
                acquired_at=datetime(2023, 1, 1, tzinfo=UTC),
                used_at=datetime(2025, 1, 2, tzinfo=UTC),
                quantity=Decimal("1"),
                cost_basis_eur=Decimal("1200"),
                value_eur=Decimal("2000"),
            )
        ],
    )

    summary = TaxSummaryService().build_summary(
        TaxCalculationResult(disposals=[short_disposal, long_disposal], open_lots=[])
    )

    assert summary.taxable_gain_eur == Decimal("2000")
    assert summary.long_held_gain_eur == Decimal("800")
    assert summary.total_gain_eur == Decimal("2800")
    assert summary.rows[0].classification == "short_held"
    assert summary.rows[1].classification == "long_held"
