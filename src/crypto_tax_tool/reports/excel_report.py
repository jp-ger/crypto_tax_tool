from pathlib import Path

from openpyxl import Workbook

from crypto_tax_tool.services.tax_summary import TaxSummary


class ExcelTaxReportExporter:
    def export(self, summary: TaxSummary, path: Path) -> Path:
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

        workbook.save(path)
        return path
