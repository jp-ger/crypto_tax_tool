from datetime import UTC, datetime
from decimal import Decimal

from crypto_tax_tool.models.fifo_state import LotUsage
from crypto_tax_tool.reports.audit_report import AuditCsvExporter
from crypto_tax_tool.services.audit_service import AuditTrailService
from crypto_tax_tool.services.tax_engine import DisposalResult, TaxCalculationResult


def test_audit_trail_links_disposal_to_fifo_usage(tmp_path) -> None:
    disposal = DisposalResult(
        transaction_id="sell1",
        asset="BTC",
        quantity=Decimal("0.1"),
        proceeds_eur=Decimal("5000"),
        matches=[
            LotUsage(
                lot_id="lot1",
                asset="BTC",
                acquired_at=datetime(2024, 1, 1, tzinfo=UTC),
                used_at=datetime(2025, 1, 1, tzinfo=UTC),
                quantity=Decimal("0.1"),
                cost_basis_eur=Decimal("3000"),
                value_eur=Decimal("5000"),
                source_transaction_id="buy1",
            )
        ],
    )
    records = AuditTrailService().build_report_audit(
        TaxCalculationResult(disposals=[disposal], open_lots=[])
    )

    assert len(records) == 1
    assert records[0].disposal_transaction_id == "sell1"
    assert records[0].lot_links[0].lot_id == "lot1"
    assert records[0].lot_links[0].source_transaction_id == "buy1"

    path = AuditCsvExporter().export(records, tmp_path / "audit.csv")
    content = path.read_text(encoding="utf-8")
    assert "disposal_transaction_id" in content
    assert "sell1" in content
    assert "buy1" in content
