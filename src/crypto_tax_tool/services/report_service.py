from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from crypto_tax_tool.database.loaders import load_transactions
from crypto_tax_tool.database.manual_store import load_manual_lots
from crypto_tax_tool.reports.audit_report import AuditCsvExporter
from crypto_tax_tool.reports.csv_report import CsvIncomeReportExporter, CsvTaxReportExporter
from crypto_tax_tool.reports.excel_report import ExcelTaxReportExporter
from crypto_tax_tool.services.audit_service import AuditTrailService
from crypto_tax_tool.services.backup_service import BackupService
from crypto_tax_tool.services.binance_price_provider import BinanceHistoricalPriceProvider
from crypto_tax_tool.services.pricing import HistoricalPriceService
from crypto_tax_tool.services.tax_engine import TaxCalculationResult, TaxEngine
from crypto_tax_tool.services.tax_summary import TaxSummaryService
from crypto_tax_tool.services.validation_service import ValidationReport, ValidationService
from crypto_tax_tool.settings import get_settings


class ReportValidationError(RuntimeError):
    def __init__(self, validation_report: ValidationReport) -> None:
        self.validation_report = validation_report
        messages = "; ".join(issue.message for issue in validation_report.errors)
        super().__init__(messages or "Validation failed.")


@dataclass(frozen=True)
class ReportGenerationResult:
    output_dir: Path
    summary_csv: Path
    summary_xlsx: Path
    audit_csv: Path
    income_csv: Path
    transactions: int
    disposals: int
    income_events: int
    open_lots: int
    validation_report: ValidationReport
    backup_path: Path | None
    manual_lots: int


class ReportGenerationService:
    def generate_tax_report(
        self,
        output_dir: Path | None = None,
        report_start: datetime | None = None,
        report_end: datetime | None = None,
        number_format: str = "international",
    ) -> ReportGenerationResult:
        validation_report = ValidationService().validate()
        if not validation_report.can_create_report:
            raise ReportValidationError(validation_report)

        backup = BackupService().create_backup("before_report")
        transactions = load_transactions()
        manual_lots = load_manual_lots()
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        if output_dir is None:
            output_dir = get_settings().data_dir / "reports" / f"tax_report_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)

        price_service = HistoricalPriceService(providers=[BinanceHistoricalPriceProvider()])
        full_calculation = TaxEngine(price_service, initial_lots=manual_lots).calculate(transactions)
        calculation = self._filter_calculation(full_calculation, report_start, report_end)
        summary = TaxSummaryService().build_summary(calculation)
        audit_records = AuditTrailService().build_report_audit(calculation)

        summary_csv = CsvTaxReportExporter().export(
            summary, output_dir / "tax_summary.csv", number_format=number_format
        )
        income_csv = CsvIncomeReportExporter().export(
            summary, output_dir / "taxable_income.csv", number_format=number_format
        )
        summary_xlsx = ExcelTaxReportExporter().export(
            summary,
            output_dir / "tax_report.xlsx",
            calculation.open_lots,
            number_format=number_format,
        )
        audit_csv = AuditCsvExporter().export(audit_records, output_dir / "audit_trail.csv")

        return ReportGenerationResult(
            output_dir=output_dir,
            summary_csv=summary_csv,
            summary_xlsx=summary_xlsx,
            audit_csv=audit_csv,
            income_csv=income_csv,
            transactions=len(transactions),
            disposals=len(calculation.disposals),
            income_events=len(calculation.income_events or []),
            open_lots=len(calculation.open_lots),
            validation_report=validation_report,
            backup_path=backup.path,
            manual_lots=len(manual_lots),
        )

    @staticmethod
    def _filter_calculation(
        calculation: TaxCalculationResult,
        report_start: datetime | None,
        report_end: datetime | None,
    ) -> TaxCalculationResult:
        if report_start is None and report_end is None:
            return calculation
        report_start = _as_utc(report_start)
        report_end = _as_utc(report_end)
        disposals = []
        for disposal in calculation.disposals:
            disposed_at = _as_utc(disposal.disposed_at)
            if disposed_at is None:
                disposals.append(disposal)
                continue
            if report_start is not None and disposed_at < report_start:
                continue
            if report_end is not None and disposed_at > report_end:
                continue
            disposals.append(disposal)
        income_events = []
        for income in calculation.income_events or []:
            received_at = _as_utc(income.received_at)
            if received_at is None:
                income_events.append(income)
                continue
            if report_start is not None and received_at < report_start:
                continue
            if report_end is not None and received_at > report_end:
                continue
            income_events.append(income)
        return TaxCalculationResult(
            disposals=disposals,
            open_lots=calculation.open_lots,
            income_events=income_events,
        )


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
