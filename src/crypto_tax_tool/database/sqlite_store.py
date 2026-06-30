import json
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from crypto_tax_tool.models.transactions import NormalizedTransaction
from crypto_tax_tool.settings import get_settings


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    kind TEXT NOT NULL,
    category TEXT NOT NULL,
    asset TEXT NOT NULL,
    quantity TEXT NOT NULL,
    quote_asset TEXT,
    quote_quantity TEXT,
    fee_asset TEXT,
    fee_quantity TEXT,
    side TEXT,
    product TEXT,
    raw_type TEXT,
    extra_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_transactions_timestamp ON transactions(timestamp);
CREATE INDEX IF NOT EXISTS idx_transactions_asset ON transactions(asset);
CREATE INDEX IF NOT EXISTS idx_transactions_kind ON transactions(kind);

CREATE TABLE IF NOT EXISTS sync_state (
    sync_key TEXT PRIMARY KEY,
    sync_value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def get_db_path() -> Path:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings.db_path


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def initialize_sqlite() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()


def _decimal_to_text(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def save_transactions(rows: list[NormalizedTransaction]) -> int:
    if not rows:
        return 0
    inserted = 0
    with connect() as conn:
        for tx in rows:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO transactions (
                    id, source, source_id, timestamp, kind, category, asset, quantity,
                    quote_asset, quote_quantity, fee_asset, fee_quantity, side, product,
                    raw_type, extra_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tx.id,
                    tx.source.value,
                    tx.source_id,
                    tx.timestamp.isoformat(),
                    tx.kind.value,
                    tx.tax_category.value,
                    tx.asset,
                    str(tx.quantity),
                    tx.quote_asset,
                    _decimal_to_text(tx.quote_quantity),
                    tx.fee_asset,
                    _decimal_to_text(tx.fee_quantity),
                    tx.side.value if tx.side else None,
                    tx.product,
                    tx.raw_type,
                    json.dumps(tx.metadata, ensure_ascii=False, default=str),
                    tx.created_at.isoformat(),
                ),
            )
            inserted += cursor.rowcount
        conn.commit()
    return inserted


def set_sync_state(key: str, value: str) -> None:
    now = datetime.now(UTC).isoformat()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO sync_state (sync_key, sync_value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(sync_key) DO UPDATE SET
                sync_value = excluded.sync_value,
                updated_at = excluded.updated_at
            """,
            (key, value, now),
        )
        conn.commit()


def get_sync_state(key: str) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT sync_value FROM sync_state WHERE sync_key = ?", (key,)).fetchone()
        return None if row is None else str(row["sync_value"])


def count_transactions() -> int:
    with connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM transactions").fetchone()
        return int(row["n"])
