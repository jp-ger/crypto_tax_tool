from crypto_tax_tool.models.audit import AuditDisposalRecord, AuditLotLink
from crypto_tax_tool.services.tax_engine import DisposalResult, TaxCalculationResult


class AuditTrailService:
    def build_disposal_audit(self, disposal: DisposalResult) -> AuditDisposalRecord:
        return AuditDisposalRecord(
            disposal_transaction_id=disposal.transaction_id,
            asset=disposal.asset,
            quantity=disposal.quantity,
            proceeds_eur=disposal.proceeds_eur,
            cost_basis_eur=disposal.cost_basis_eur,
            gain_eur=disposal.gain_eur,
            lot_links=[
                AuditLotLink(
                    lot_id=match.lot_id,
                    source_transaction_id=match.lot_id,
                    acquired_at=match.acquired_at,
                    quantity=match.quantity,
                    cost_basis_eur=match.cost_basis_eur,
                )
                for match in disposal.matches
            ],
        )

    def build_report_audit(self, result: TaxCalculationResult) -> list[AuditDisposalRecord]:
        return [self.build_disposal_audit(disposal) for disposal in result.disposals]
