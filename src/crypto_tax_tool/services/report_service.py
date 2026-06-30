from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from crypto_tax_tool.database.loaders import load_transactions
from crypto_tax_tool.reports.audit_report import AuditCsvExporter
from crypto_tax_tool.reports.csv_report import CsvTaxReportExporter
from crypto_tax_tool.reports.excel_report import ExcelTaxReportExporter
from crypto_tax_tool.services.audit_service import AuditTrailService
from crypto_tax_tool.services.binance_price_provider import BinanceHistoricalPriceProvider
from crypto_tax_tool.services.pricing import HistoricalPriceService
from crypto_tax_tool.services.tax_engine import TaxEngine
from crypto_tax_tool.services.tax_summary import TaxSummaryService
from crypto_tax_tool.settings import get_settings


@dataclass(frozen=True)
class ReportGenerationResult:
    output_dir: Path
    summary_csv: Path
    summary_xlsx: Path
    audit_csv: Path
    transactions: int
    disposals: int
    open_lots: int


class ReportGenerationService:
    def generate_tax_report(self, output_dir: Path | None = None) -> ReportGenerationResult:
        transactions = load_transactions()
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        if output_dir is None:
            output_dir = get_settings().data_dir / "reports" / f"tax_report_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)

        price_service = HistoricalPriceService(providers=[BinanceHistoricalPriceProvider()])
        calculation = TaxEngine(price_service).calculate(transactions)
        summary = TaxSummaryService().build_summary(calculation)
        audit_records = AuditTrailService().build_report_audit(calculation)

        summary_csv = CsvTaxReportExporter().export(summary, output_dir / "tax_summary.csv")
        summary_xlsx = ExcelTaxReportExporter().export(
            summary, output_dir / "tax_report.xlsx", calculation.open_lots
        )
        audit_csv = AuditCsvExporter().export(audit_records, output_dir / "audit_trail.csv")

        return ReportGenerationResult(
            output_dir=output_dir,
            summary_csv=summary_csv,
            summary_xlsx=summary_xlsx,
            audit_csv=audit_csv,
            transactions=len(transactions),
            disposals=len(calculation.disposals),
            open_lots=len(calculation.open_lots),
        )
