import csv
from pathlib import Path

from crypto_tax_tool.services.tax_summary import TaxSummary


class CsvTaxReportExporter:
    def export(self, summary: TaxSummary, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, delimiter=";")
            writer.writerow(
                [
                    "transaction_id",
                    "asset",
                    "quantity",
                    "proceeds_eur",
                    "cost_basis_eur",
                    "gain_eur",
                    "holding_days_min",
                    "holding_days_max",
                    "classification",
                ]
            )
            for row in summary.rows:
                writer.writerow(
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
        return path


class CsvIncomeReportExporter:
    def export(self, summary: TaxSummary, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, delimiter=";")
            writer.writerow(
                [
                    "transaction_id",
                    "received_at",
                    "asset",
                    "quantity",
                    "income_eur",
                    "eur_price",
                    "product",
                    "raw_type",
                    "price_provider",
                    "price_pair",
                ]
            )
            for row in summary.income_rows:
                writer.writerow(
                    [
                        row.transaction_id,
                        row.received_at,
                        row.asset,
                        str(row.quantity),
                        str(row.income_eur),
                        str(row.price_eur),
                        row.product,
                        row.raw_type,
                        row.price_provider,
                        row.price_pair,
                    ]
                )
        return path
