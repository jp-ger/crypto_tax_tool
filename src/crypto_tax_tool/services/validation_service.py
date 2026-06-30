from dataclasses import dataclass
from decimal import Decimal

from crypto_tax_tool.database.loaders import load_latest_balance_snapshot, load_transactions
from crypto_tax_tool.services.reconciliation import InventoryCalculator, ReconciliationService


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    message: str


@dataclass(frozen=True)
class ValidationReport:
    issues: list[ValidationIssue]

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def can_create_report(self) -> bool:
        return not self.errors


class ValidationService:
    def validate(self) -> ValidationReport:
        issues: list[ValidationIssue] = []
        transactions = load_transactions()
        if not transactions:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="no_transactions",
                    message="No transactions found. Run Binance sync before creating a report.",
                )
            )
            return ValidationReport(issues=issues)

        duplicate_source_ids = self._duplicate_source_ids(transactions)
        if duplicate_source_ids:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="duplicate_source_ids",
                    message=f"Duplicate transaction source IDs found: {len(duplicate_source_ids)}.",
                )
            )

        expected = InventoryCalculator().calculate(transactions)
        negative_assets = {asset: amount for asset, amount in expected.items() if amount < Decimal("-0.00000001")}
        if negative_assets:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="negative_expected_balances",
                    message=f"Negative expected balances detected for {len(negative_assets)} assets.",
                )
            )

        snapshot = load_latest_balance_snapshot()
        if snapshot is None:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="missing_balance_snapshot",
                    message="No Binance balance snapshot found. Reconciliation cannot be checked.",
                )
            )
        else:
            actual = {row.asset: row.total for row in snapshot.balances}
            reconciliation = ReconciliationService(tolerance=Decimal("0.00000001")).compare(expected, actual)
            errors = [row for row in reconciliation.rows if row.status == "error"]
            warnings = [row for row in reconciliation.rows if row.status == "warning"]
            if errors:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        code="reconciliation_errors",
                        message=f"Reconciliation differences detected for {len(errors)} assets.",
                    )
                )
            if warnings:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        code="reconciliation_warnings",
                        message=f"Small reconciliation differences detected for {len(warnings)} assets.",
                    )
                )

        return ValidationReport(issues=issues)

    @staticmethod
    def _duplicate_source_ids(transactions) -> set[str]:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for tx in transactions:
            key = f"{tx.source.value}:{tx.source_id}"
            if key in seen:
                duplicates.add(key)
            seen.add(key)
        return duplicates
