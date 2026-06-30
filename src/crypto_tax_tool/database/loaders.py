import json
from datetime import datetime
from decimal import Decimal

from crypto_tax_tool.database.sqlite_store import connect
from crypto_tax_tool.models.balances import AssetBalance, BalanceSnapshot
from crypto_tax_tool.models.enums import TaxCategory, TradeSide, TransactionKind, TransactionSource
from crypto_tax_tool.models.transactions import NormalizedTransaction


def _decimal(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)


def load_transactions() -> list[NormalizedTransaction]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM transactions
            ORDER BY timestamp, source_id
            """
        ).fetchall()

    result: list[NormalizedTransaction] = []
    for row in rows:
        result.append(
            NormalizedTransaction(
                id=row["id"],
                source=TransactionSource(row["source"]),
                source_id=row["source_id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                kind=TransactionKind(row["kind"]),
                tax_category=TaxCategory(row["category"]),
                asset=row["asset"],
                quantity=Decimal(row["quantity"]),
                quote_asset=row["quote_asset"],
                quote_quantity=_decimal(row["quote_quantity"]),
                fee_asset=row["fee_asset"],
                fee_quantity=_decimal(row["fee_quantity"]),
                side=TradeSide(row["side"]) if row["side"] else None,
                product=row["product"],
                raw_type=row["raw_type"],
                metadata=json.loads(row["extra_json"]),
                created_at=datetime.fromisoformat(row["created_at"]),
            )
        )
    return result


def load_latest_balance_snapshot() -> BalanceSnapshot | None:
    with connect() as conn:
        snapshot_row = conn.execute(
            """
            SELECT * FROM balance_snapshots
            ORDER BY timestamp DESC
            LIMIT 1
            """
        ).fetchone()
        if snapshot_row is None:
            return None
        balance_rows = conn.execute(
            """
            SELECT * FROM balance_rows
            WHERE snapshot_id = ?
            ORDER BY asset
            """,
            (snapshot_row["id"],),
        ).fetchall()

    return BalanceSnapshot(
        id=snapshot_row["id"],
        source=TransactionSource(snapshot_row["source"]),
        timestamp=datetime.fromisoformat(snapshot_row["timestamp"]),
        balances=[
            AssetBalance(
                asset=row["asset"],
                free=Decimal(row["free"]),
                locked=Decimal(row["locked"]),
            )
            for row in balance_rows
        ],
    )
