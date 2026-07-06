import csv
from decimal import Decimal
from pathlib import Path

from crypto_tax_tool.services.tax_summary import TaxSummary


GERMAN_NUMBER_FORMATS = {"german", "de", "de_DE", "european"}


def _format_decimal(value: Decimal, number_format: str) -> str:
    text = format(value, "f")
    if number_format in GERMAN_NUMBER_FORMATS:
        return text.replace(".", ",")
    return text


class CsvTaxReportExporter:
    def export(self, summary: TaxSummary, path: Path, number_format: str = "international") -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
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
                        _format_decimal(row.quantity, number_format),
                        _format_decimal(row.proceeds_eur, number_format),
                        _format_decimal(row.cost_basis_eur, number_format),
                        _format_decimal(row.gain_eur, number_format),
                        row.holding_days_min,
                        row.holding_days_max,
                        row.classification,
                    ]
                )
        return path


class CsvIncomeReportExporter:
    def export(self, summary: TaxSummary, path: Path, number_format: str = "international") -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
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
                        _format_decimal(row.quantity, number_format),
                        _format_decimal(row.income_eur, number_format),
                        _format_decimal(row.price_eur, number_format),
                        row.product,
                        row.raw_type,
                        row.price_provider,
                        row.price_pair,
                    ]
                )
        return path
