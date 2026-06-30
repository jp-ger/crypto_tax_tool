from datetime import datetime

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
            client = BinanceClient()
            self.log.emit("Starting Binance synchronization")
            result: SyncResult = SyncService(client).sync(start=self.start, end=self.end)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
        else:
            self.finished.emit(result)
