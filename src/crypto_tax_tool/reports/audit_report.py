import csv
from pathlib import Path

from crypto_tax_tool.models.audit import AuditDisposalRecord


class AuditCsvExporter:
    def export(self, records: list[AuditDisposalRecord], path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, delimiter=";")
            writer.writerow(
                [
                    "disposal_transaction_id",
                    "asset",
                    "disposed_quantity",
                    "proceeds_eur",
                    "cost_basis_eur",
                    "gain_eur",
                    "lot_id",
                    "source_transaction_id",
                    "acquired_at",
                    "lot_quantity",
                    "lot_cost_basis_eur",
                ]
            )
            for record in records:
                for link in record.lot_links:
                    writer.writerow(
                        [
                            record.disposal_transaction_id,
                            record.asset,
                            str(record.quantity),
                            str(record.proceeds_eur),
                            str(record.cost_basis_eur),
                            str(record.gain_eur),
                            link.lot_id,
                            link.source_transaction_id,
                            link.acquired_at.isoformat(),
                            str(link.quantity),
                            str(link.cost_basis_eur),
                        ]
                    )
        return path
