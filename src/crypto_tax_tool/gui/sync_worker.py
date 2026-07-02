from datetime import datetime
import traceback

from PySide6.QtCore import QObject, Signal, Slot

from crypto_tax_tool.api.binance.client import BinanceClient
from crypto_tax_tool.services.sync_service import SyncService, SyncResult


class SyncWorker(QObject):
    log = Signal(str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, start: datetime, end: datetime) -> None:
        super().__init__()
        self.start = start
        self.end = end

    @Slot()
    def run(self) -> None:
        try:
            self.log.emit("Creating Binance client")
            client = BinanceClient(progress_callback=self.log.emit)
            self.log.emit("Starting Binance synchronization")
            result: SyncResult = SyncService(client, progress_callback=self.log.emit).sync(
                start=self.start,
                end=self.end,
            )
        except Exception as exc:  # noqa: BLE001
            message = f"{type(exc).__name__}: {exc}"
            self.log.emit(f"ERROR during Binance sync: {message}")
            self.log.emit(traceback.format_exc())
            self.failed.emit(message)
        else:
            self.finished.emit(result)
