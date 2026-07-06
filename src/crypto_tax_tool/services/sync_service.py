from collections.abc import Callable
from datetime import datetime

from crypto_tax_tool.api.exchange_base import ExchangeClient
from crypto_tax_tool.database.sqlite_store import save_balance_snapshot, save_transactions, set_sync_state
from crypto_tax_tool.models.transactions import NormalizedTransaction
from crypto_tax_tool.services.backup_service import BackupService


class SyncResult:
    def __init__(self, loaded: int, inserted: int, balance_rows: int = 0, backup_path: str | None = None) -> None:
        self.loaded = loaded
        self.inserted = inserted
        self.balance_rows = balance_rows
        self.backup_path = backup_path


class SyncService:
    def __init__(self, exchange_client: ExchangeClient, progress_callback: Callable[[str], None] | None = None) -> None:
        self.exchange_client = exchange_client
        self.progress_callback = progress_callback

    def _log(self, message: str) -> None:
        if self.progress_callback:
            self.progress_callback(message)

    def sync(self, start: datetime, end: datetime, full_resync: bool = False) -> SyncResult:
        self._log("Creating database backup before sync...")
        backup = BackupService().create_backup("before_sync")
        if backup.path:
            self._log(f"Backup created: {backup.path}")
        else:
            self._log("No backup was created before sync.")

        if full_resync:
            self._log(
                "Full resync enabled. The selected start date will be used directly; "
                "incremental last_sync_end will be ignored for this run."
            )
            setattr(self.exchange_client, "force_full_resync", True)

        if self._supports_staged_sync():
            loaded, inserted = self._sync_and_save_staged(start=start, end=end, full_resync=full_resync)
        else:
            loaded, inserted = self._sync_and_save_all_at_once(start=start, end=end, full_resync=full_resync)

        balance_rows = 0
        if hasattr(self.exchange_client, "get_account_snapshot"):
            self._log("Loading current Binance account balance snapshot...")
            snapshot = self.exchange_client.get_account_snapshot()
            balance_rows = save_balance_snapshot(snapshot)
            set_sync_state("last_balance_snapshot", snapshot.timestamp.isoformat())
            self._log(f"Saved balance snapshot rows: {balance_rows}.")

        set_sync_state("last_sync_end", end.isoformat())
        self._log("Binance synchronization finished successfully.")
        return SyncResult(
            loaded=loaded,
            inserted=inserted,
            balance_rows=balance_rows,
            backup_path=str(backup.path) if backup.path else None,
        )

    def _supports_staged_sync(self) -> bool:
        required_methods = [
            "sync_transfers",
            "sync_convert_trades",
            "sync_asset_rewards",
            "sync_simple_earn_rewards",
            "sync_spot_trades",
        ]
        return all(hasattr(self.exchange_client, method) for method in required_methods)

    def _sync_and_save_staged(self, start: datetime, end: datetime, full_resync: bool = False) -> tuple[int, int]:
        effective_start = start
        if not full_resync and hasattr(self.exchange_client, "_effective_sync_start"):
            effective_start = self.exchange_client._effective_sync_start(start)  # noqa: SLF001

        self._log(f"Staged sync range: {effective_start.isoformat()} to {end.isoformat()}")
        stages = [
            ("Deposits and withdrawals", self.exchange_client.sync_transfers),
            ("Convert trades", self.exchange_client.sync_convert_trades),
            ("Asset rewards/dividends", self.exchange_client.sync_asset_rewards),
            ("Simple Earn rewards", self.exchange_client.sync_simple_earn_rewards),
            ("Spot trades", self.exchange_client.sync_spot_trades),
        ]

        total_loaded = 0
        total_inserted = 0
        failed_stages: list[str] = []
        for stage_name, sync_function in stages:
            self._log(f"Starting stage: {stage_name}")
            try:
                raw_rows = sync_function(effective_start, end)
            except Exception as exc:  # noqa: BLE001
                failed_stages.append(stage_name)
                self._log(
                    f"WARNING stage failed and will be skipped for this run: {stage_name}. "
                    f"Reason: {type(exc).__name__}: {exc}"
                )
                self._log(
                    "The sync will continue with the next stage. Run the same sync again later to retry this stage."
                )
                continue
            rows = self._filter_rows(raw_rows, stage_name=stage_name)
            inserted = save_transactions(rows)
            total_loaded += len(rows)
            total_inserted += inserted
            self._log(
                f"Stage saved: {stage_name}. Loaded: {len(rows)}, inserted new rows: {inserted}."
            )
        if failed_stages:
            self._log(
                "WARNING sync completed with skipped stages: "
                + ", ".join(failed_stages)
                + ". Existing/new data from successful stages was saved."
            )
        return total_loaded, total_inserted

    def _sync_and_save_all_at_once(self, start: datetime, end: datetime, full_resync: bool = False) -> tuple[int, int]:
        self._log("Loading transactions from exchange...")
        if full_resync:
            self._log("Full resync selected range is being loaded from exchange.")
        raw_rows = self.exchange_client.sync_transactions(start=start, end=end)
        rows = self._filter_rows(raw_rows, stage_name="full sync")
        self._log(f"Loaded {len(rows)} transaction rows from exchange.")

        self._log("Saving transactions to local database...")
        inserted = save_transactions(rows)
        self._log(f"Saved transactions. New rows inserted: {inserted}.")
        return len(rows), inserted

    def _filter_rows(self, raw_rows: list, stage_name: str) -> list[NormalizedTransaction]:
        rows: list[NormalizedTransaction] = [row for row in raw_rows if isinstance(row, NormalizedTransaction)]
        skipped_rows = len(raw_rows) - len(rows)
        if skipped_rows:
            self._log(f"Skipped {skipped_rows} incomplete rows in stage: {stage_name}.")
        return rows
