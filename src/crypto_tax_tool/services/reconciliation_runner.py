from decimal import Decimal

from crypto_tax_tool.database.loaders import load_latest_balance_snapshot, load_transactions
from crypto_tax_tool.services.reconciliation import InventoryCalculator, ReconciliationReport, ReconciliationService


def run_reconciliation() -> ReconciliationReport:
    transactions = load_transactions()
    snapshot = load_latest_balance_snapshot()
    if snapshot is None:
        return ReconciliationReport(rows=[])

    expected = InventoryCalculator().calculate(transactions)
    actual = {row.asset: row.total for row in snapshot.balances}
    return ReconciliationService(tolerance=Decimal("0.00000001")).compare(expected, actual)
