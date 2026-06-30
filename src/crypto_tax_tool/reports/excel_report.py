from pathlib import Path

from openpyxl import Workbook

from crypto_tax_tool.models.fifo_state import AssetLot
from crypto_tax_tool.services.tax_summary import TaxSummary


class ExcelTaxReportExporter:
    def export(self, summary: TaxSummary, path: Path, open_lots: list[AssetLot] | None = None) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Tax Summary"

        sheet.append(["Metric", "Value"])
        sheet.append(["Taxable gain EUR", str(summary.taxable_gain_eur)])
        sheet.append(["Long-held gain EUR", str(summary.long_held_gain_eur)])
        sheet.append(["Total gain EUR", str(summary.total_gain_eur)])

        details = workbook.create_sheet("Disposals")
        details.append(
            [
                "Transaction ID",
                "Asset",
                "Quantity",
                "Proceeds EUR",
                "Cost Basis EUR",
                "Gain EUR",
                "Holding Days Min",
                "Holding Days Max",
                "Classification",
            ]
        )
        for row in summary.rows:
            details.append(
                [
                    row.transaction_id,
                    row.asset,
                    str(row.quantity),
                    str(row.proceeds_eur),
                    str(row.cost_basis_eur),
                    str(row.gain_eur),
                    row.holding_days_min,
                    row.holding_days_max,
                    row.classification,
                ]
            )

        lots_sheet = workbook.create_sheet("Open Lots")
        lots_sheet.append(
            [
                "Lot ID",
                "Asset",
                "Acquired At",
                "Original Quantity",
                "Remaining Quantity",
                "Remaining Cost Basis EUR",
                "Source Transaction ID",
            ]
        )
        for lot in open_lots or []:
            lots_sheet.append(
                [
                    lot.id,
                    lot.asset,
                    lot.acquired_at.isoformat(),
                    str(lot.quantity),
                    str(lot.remaining_quantity),
                    str(lot.cost_basis_eur),
                    lot.source_transaction_id,
                ]
            )

        workbook.save(path)
        return path
