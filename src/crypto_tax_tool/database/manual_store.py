import sqlite3
from datetime import datetime
from decimal import Decimal

from crypto_tax_tool.database.sqlite_store import connect
from crypto_tax_tool.models.manual_entries import ManualChangeLogEntry, ManualLotEntry, ManualPriceEntry
from crypto_tax_tool.models.prices import HistoricalPrice


MANUAL_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS manual_prices (
    id TEXT PRIMARY KEY,
    asset TEXT NOT NULL,
    quote_asset TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    price TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS manual_lots (
    id TEXT PRIMARY KEY,
    asset TEXT NOT NULL,
    acquired_at TEXT NOT NULL,
    quantity TEXT NOT NULL,
    cost_basis_eur TEXT NOT NULL,
    reason TEXT NOT NULL,
    source_reference TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS manual_change_log (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def initialize_manual_store() -> None:
    with connect() as conn:
        conn.executescript(MANUAL_SCHEMA_SQL)
        conn.commit()


def save_manual_price(entry: ManualPriceEntry) -> bool:
    initialize_manual_store()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT OR REPLACE INTO manual_prices (
                id, asset, quote_asset, timestamp, price, reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.id,
                entry.asset,
                entry.quote_asset,
                entry.timestamp.isoformat(),
                str(entry.price),
                entry.reason,
                entry.created_at.isoformat(),
            ),
        )
        _save_change_log(
            conn,
            ManualChangeLogEntry(
                entity_type="manual_price",
                entity_id=entry.id,
                action="upsert",
                reason=entry.reason,
            ),
        )
        conn.commit()
        return cursor.rowcount == 1


def save_manual_lot(entry: ManualLotEntry) -> bool:
    initialize_manual_store()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT OR REPLACE INTO manual_lots (
                id, asset, acquired_at, quantity, cost_basis_eur,
                reason, source_reference, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.id,
                entry.asset,
                entry.acquired_at.isoformat(),
                str(entry.quantity),
                str(entry.cost_basis_eur),
                entry.reason,
                entry.source_reference,
                entry.created_at.isoformat(),
            ),
        )
        _save_change_log(
            conn,
            ManualChangeLogEntry(
                entity_type="manual_lot",
                entity_id=entry.id,
                action="upsert",
                reason=entry.reason,
            ),
        )
        conn.commit()
        return cursor.rowcount == 1


def get_manual_price(asset: str, quote_asset: str, timestamp: datetime) -> HistoricalPrice | None:
    initialize_manual_store()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, asset, quote_asset, timestamp, price
            FROM manual_prices
            WHERE asset = ? AND quote_asset = ? AND timestamp = ?
            LIMIT 1
            """,
            (asset, quote_asset, timestamp.isoformat()),
        ).fetchone()
    if row is None:
        return None
    return HistoricalPrice(
        id=row["id"],
        asset=row["asset"],
        quote_asset=row["quote_asset"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        price=Decimal(row["price"]),
        provider="manual",
        pair=f"{asset}{quote_asset}",
    )


def count_manual_entries() -> int:
    initialize_manual_store()
    with connect() as conn:
        prices = conn.execute("SELECT COUNT(*) AS n FROM manual_prices").fetchone()["n"]
        lots = conn.execute("SELECT COUNT(*) AS n FROM manual_lots").fetchone()["n"]
        return int(prices) + int(lots)


def count_manual_change_log() -> int:
    initialize_manual_store()
    with connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM manual_change_log").fetchone()
        return int(row["n"])


def _save_change_log(conn: sqlite3.Connection, entry: ManualChangeLogEntry) -> None:
    conn.execute(
        """
        INSERT INTO manual_change_log (
            id, entity_type, entity_id, action, reason, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            entry.id,
            entry.entity_type,
            entry.entity_id,
            entry.action,
            entry.reason,
            entry.created_at.isoformat(),
        ),
    )
