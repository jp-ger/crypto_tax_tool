from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from crypto_tax_tool.database.loaders import load_transactions
from crypto_tax_tool.database.manual_store import load_manual_lots
from crypto_tax_tool.reports.audit_report import AuditCsvExporter
from crypto_tax_tool.reports.csv_report import CsvIncomeReportExporter, CsvMissingInventoryExporter, CsvTaxReportExporter
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
    missing_inventory_csv: Path
    transactions: int
    disposals: int
    income_events: int
    open_lots: int
    validation_report: ValidationReport
    backup_path: Path | None
    manual_lots: int
    missing_inventory_issues: int


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
        # Prefetch historical prices used by the tax engine to avoid repeated
        # DB/API lookups during calculation. Collect unique (asset, quote, hour)
        # tuples and request them once.
        price_service = HistoricalPriceService(providers=[BinanceHistoricalPriceProvider()])
        self._prefetch_prices(transactions, manual_lots, price_service)
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        if output_dir is None:
            output_dir = get_settings().data_dir / "reports" / f"tax_report_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)

        full_calculation = TaxEngine(price_service, initial_lots=manual_lots).calculate(transactions)
        calculation = self._filter_calculation(full_calculation, report_start, report_end)
        summary = TaxSummaryService().build_summary(calculation)
        audit_records = AuditTrailService().build_report_audit(calculation)
        missing_inventory_issues = calculation.missing_inventory_issues or []

        summary_csv = CsvTaxReportExporter().export(
            summary, output_dir / "tax_summary.csv", number_format=number_format
        )
        income_csv = CsvIncomeReportExporter().export(
            summary, output_dir / "taxable_income.csv", number_format=number_format
        )
        missing_inventory_csv = CsvMissingInventoryExporter().export(
            missing_inventory_issues,
            output_dir / "missing_inventory.csv",
            number_format=number_format,
        )
        summary_xlsx = ExcelTaxReportExporter().export(
            summary,
            output_dir / "tax_report.xlsx",
            calculation.open_lots,
            number_format=number_format,
            missing_inventory_issues=missing_inventory_issues,
        )
        audit_csv = AuditCsvExporter().export(audit_records, output_dir / "audit_trail.csv")

        return ReportGenerationResult(
            output_dir=output_dir,
            summary_csv=summary_csv,
            summary_xlsx=summary_xlsx,
            audit_csv=audit_csv,
            income_csv=income_csv,
            missing_inventory_csv=missing_inventory_csv,
            transactions=len(transactions),
            disposals=len(calculation.disposals),
            income_events=len(calculation.income_events or []),
            open_lots=len(calculation.open_lots),
            validation_report=validation_report,
            backup_path=backup.path,
            manual_lots=len(manual_lots),
            missing_inventory_issues=len(missing_inventory_issues),
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
        missing_inventory_issues = []
        for issue in calculation.missing_inventory_issues or []:
            disposed_at = _as_utc(issue.disposed_at)
            if disposed_at is None:
                missing_inventory_issues.append(issue)
                continue
            if report_start is not None and disposed_at < report_start:
                continue
            if report_end is not None and disposed_at > report_end:
                continue
            missing_inventory_issues.append(issue)
        return TaxCalculationResult(
            disposals=disposals,
            open_lots=calculation.open_lots,
            income_events=income_events,
            missing_inventory_issues=missing_inventory_issues,
        )

    def _prefetch_prices(self, transactions: list, manual_lots: list, price_service: HistoricalPriceService) -> None:
        from crypto_tax_tool.services.pricing import PriceNotFoundError

        keys: set[tuple[str, str]] = set()
        # For each transaction, we need the asset->EUR price. If a quote_asset exists
        # and is not EUR, also prefetch quote_asset->EUR since the engine may use it.
        for tx in transactions:
            asset = getattr(tx, "asset", None)
            if asset:
                keys.add((asset.upper(), "EUR"))
            quote = getattr(tx, "quote_asset", None)
            if quote and quote.upper() != "EUR":
                keys.add((quote.upper(), "EUR"))

        # Manual lots may reference assets that appear as open lots; ensure their prices are available.
        for lot in manual_lots:
            keys.add((lot.asset.upper(), "EUR"))

        # Request prices for the hour-floor of each transaction timestamp.
        # Use the price_service.get_price which will save/cache prices.
        timestamps_by_asset: dict[tuple[str, str], set] = {}
        for tx in transactions:
            ts = tx.timestamp
            for asset_key in list(keys):
                asset_name, quote = asset_key
                timestamps_by_asset.setdefault(asset_key, set()).add(ts)

        for (asset, quote), ts_set in timestamps_by_asset.items():
            for ts in sorted(ts_set):
                try:
                    price_service.get_price(asset, quote, ts)
                except PriceNotFoundError:
                    # Missing price for this hour — leave it to the engine which will raise if needed.
                    continue


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
