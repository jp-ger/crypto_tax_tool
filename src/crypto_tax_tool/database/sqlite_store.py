import json
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from crypto_tax_tool.models.balances import BalanceSnapshot
from crypto_tax_tool.models.fifo_state import AssetLot, LotUsage
from crypto_tax_tool.models.prices import HistoricalPrice
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

CREATE TABLE IF NOT EXISTS balance_snapshots (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS balance_rows (
    snapshot_id TEXT NOT NULL,
    asset TEXT NOT NULL,
    free TEXT NOT NULL,
    locked TEXT NOT NULL,
    total TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, asset),
    FOREIGN KEY (snapshot_id) REFERENCES balance_snapshots(id)
);

CREATE INDEX IF NOT EXISTS idx_balance_rows_asset ON balance_rows(asset);

CREATE TABLE IF NOT EXISTS historical_prices (
    id TEXT PRIMARY KEY,
    asset TEXT NOT NULL,
    quote_asset TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    price TEXT NOT NULL,
    provider TEXT NOT NULL,
    pair TEXT,
    UNIQUE(asset, quote_asset, timestamp, provider)
);

CREATE INDEX IF NOT EXISTS idx_historical_prices_lookup
ON historical_prices(asset, quote_asset, timestamp);

CREATE TABLE IF NOT EXISTS fifo_lots (
    id TEXT PRIMARY KEY,
    asset TEXT NOT NULL,
    acquired_at TEXT NOT NULL,
    quantity TEXT NOT NULL,
    remaining_quantity TEXT NOT NULL,
    cost_basis_eur TEXT NOT NULL,
    source_transaction_id TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fifo_lots_asset ON fifo_lots(asset);
CREATE INDEX IF NOT EXISTS idx_fifo_lots_acquired_at ON fifo_lots(acquired_at);

CREATE TABLE IF NOT EXISTS fifo_usages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    disposal_transaction_id TEXT NOT NULL,
    lot_id TEXT NOT NULL,
    asset TEXT NOT NULL,
    acquired_at TEXT NOT NULL,
    used_at TEXT NOT NULL,
    quantity TEXT NOT NULL,
    cost_basis_eur TEXT NOT NULL,
    value_eur TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fifo_usages_disposal ON fifo_usages(disposal_transaction_id);
CREATE INDEX IF NOT EXISTS idx_fifo_usages_lot ON fifo_usages(lot_id);
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


def save_balance_snapshot(snapshot: BalanceSnapshot) -> int:
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO balance_snapshots (id, source, timestamp)
            VALUES (?, ?, ?)
            """,
            (snapshot.id, snapshot.source.value, snapshot.timestamp.isoformat()),
        )
        conn.execute("DELETE FROM balance_rows WHERE snapshot_id = ?", (snapshot.id,))
        for row in snapshot.balances:
            conn.execute(
                """
                INSERT INTO balance_rows (snapshot_id, asset, free, locked, total)
                VALUES (?, ?, ?, ?, ?)
                """,
                (snapshot.id, row.asset, str(row.free), str(row.locked), str(row.total)),
            )
        conn.commit()
    return len(snapshot.balances)


def save_fifo_lots(lots: list[AssetLot]) -> int:
    with connect() as conn:
        conn.execute("DELETE FROM fifo_lots")
        for lot in lots:
            conn.execute(
                """
                INSERT INTO fifo_lots (
                    id, asset, acquired_at, quantity, remaining_quantity,
                    cost_basis_eur, source_transaction_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    lot.id,
                    lot.asset,
                    lot.acquired_at.isoformat(),
                    str(lot.quantity),
                    str(lot.remaining_quantity),
                    str(lot.cost_basis_eur),
                    lot.source_transaction_id,
                ),
            )
        conn.commit()
    return len(lots)


def save_fifo_usages(disposal_transaction_id: str, usages: list[LotUsage]) -> int:
    with connect() as conn:
        conn.execute(
            "DELETE FROM fifo_usages WHERE disposal_transaction_id = ?",
            (disposal_transaction_id,),
        )
        for usage in usages:
            conn.execute(
                """
                INSERT INTO fifo_usages (
                    disposal_transaction_id, lot_id, asset, acquired_at, used_at,
                    quantity, cost_basis_eur, value_eur
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    disposal_transaction_id,
                    usage.lot_id,
                    usage.asset,
                    usage.acquired_at.isoformat(),
                    usage.used_at.isoformat(),
                    str(usage.quantity),
                    str(usage.cost_basis_eur),
                    str(usage.value_eur),
                ),
            )
        conn.commit()
    return len(usages)


def save_price(price: HistoricalPrice) -> bool:
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO historical_prices (
                id, asset, quote_asset, timestamp, price, provider, pair
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                price.id,
                price.asset,
                price.quote_asset,
                price.timestamp.isoformat(),
                str(price.price),
                price.provider,
                price.pair,
            ),
        )
        conn.commit()
        return cursor.rowcount == 1


def get_cached_price(asset: str, quote_asset: str, timestamp: datetime) -> HistoricalPrice | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, asset, quote_asset, timestamp, price, provider, pair
            FROM historical_prices
            WHERE asset = ? AND quote_asset = ? AND timestamp = ?
            ORDER BY provider
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
        provider=row["provider"],
        pair=row["pair"],
    )


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


def count_balance_rows() -> int:
    with connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM balance_rows").fetchone()
        return int(row["n"])


def count_prices() -> int:
    with connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM historical_prices").fetchone()
        return int(row["n"])


def count_fifo_lots() -> int:
    with connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM fifo_lots").fetchone()
        return int(row["n"])


def count_fifo_usages() -> int:
    with connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM fifo_usages").fetchone()
        return int(row["n"])
