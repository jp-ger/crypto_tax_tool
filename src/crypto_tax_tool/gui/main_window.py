from datetime import datetime

from PySide6.QtCore import QThread
from PySide6.QtWidgets import (
    QDateEdit,
    QLabel,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from crypto_tax_tool.api.binance.client import BinanceClient
from crypto_tax_tool.database.sqlite_store import count_balance_rows, count_transactions
from crypto_tax_tool.gui.sync_worker import SyncWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Crypto Tax Tool")
        self.resize(900, 650)
        self.sync_thread: QThread | None = None
        self.sync_worker: SyncWorker | None = None

        self.status_label = QLabel("Ready. Use read-only API credentials.")
        self.count_label = QLabel(self._local_count_text())

        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.start_date.setDate(self.start_date.date().addYears(-1))

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        self.end_date.setDate(self.end_date.date().currentDate())

        self.test_button = QPushButton("Test Binance connection")
        self.test_button.clicked.connect(self._test_binance_connection)

        self.sync_button = QPushButton("Start Binance sync")
        self.sync_button.clicked.connect(self._run_sync)

        self.refresh_button = QPushButton("Refresh local counts")
        self.refresh_button.clicked.connect(self._refresh_count)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Crypto Tax Tool"))
        layout.addWidget(self.status_label)
        layout.addWidget(self.count_label)
        layout.addWidget(QLabel("Sync start date"))
        layout.addWidget(self.start_date)
        layout.addWidget(QLabel("Sync end date"))
        layout.addWidget(self.end_date)
        layout.addWidget(self.test_button)
        layout.addWidget(self.sync_button)
        layout.addWidget(self.refresh_button)
        layout.addWidget(QLabel("Status log"))
        layout.addWidget(self.log_box)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def _local_count_text(self) -> str:
        return f"Local transactions: {count_transactions()} | Balance rows: {count_balance_rows()}"

    def _refresh_count(self) -> None:
        self.count_label.setText(self._local_count_text())

    def _append_log(self, message: str) -> None:
        self.log_box.append(message)

    def _test_binance_connection(self) -> None:
        try:
            BinanceClient().test_connection()
        except Exception as exc:  # noqa: BLE001
            self.status_label.setText(f"Connection failed: {exc}")
            self._append_log(f"Connection failed: {exc}")
        else:
            self.status_label.setText("Binance API is reachable.")
            self._append_log("Binance API is reachable.")

    def _run_sync(self) -> None:
        start = datetime.combine(self.start_date.date().toPython(), datetime.min.time())
        end = datetime.combine(self.end_date.date().toPython(), datetime.max.time())
        self.status_label.setText("Sync running in background.")
        self._append_log(f"Starting sync from {start.isoformat()} to {end.isoformat()}")
        self.sync_button.setEnabled(False)

        self.sync_thread = QThread()
        self.sync_worker = SyncWorker(start=start, end=end)
        self.sync_worker.moveToThread(self.sync_thread)
        self.sync_thread.started.connect(self.sync_worker.run)
        self.sync_worker.log.connect(self._append_log)
        self.sync_worker.finished.connect(self._sync_finished)
        self.sync_worker.failed.connect(self._sync_failed)
        self.sync_worker.finished.connect(self.sync_thread.quit)
        self.sync_worker.failed.connect(self.sync_thread.quit)
        self.sync_thread.finished.connect(self._sync_thread_finished)
        self.sync_thread.start()

    def _sync_finished(self, result) -> None:
        self.status_label.setText("Sync completed.")
        self._append_log(
            f"Sync completed. Loaded: {result.loaded}, inserted: {result.inserted}, "
            f"balance rows: {result.balance_rows}"
        )
        self._refresh_count()

    def _sync_failed(self, message: str) -> None:
        self.status_label.setText(f"Sync failed: {message}")
        self._append_log(f"Sync failed: {message}")

    def _sync_thread_finished(self) -> None:
        self.sync_button.setEnabled(True)
        self.sync_worker = None
        self.sync_thread = None
