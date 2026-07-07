from datetime import datetime
from decimal import Decimal

from PySide6.QtCore import QThread
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from crypto_tax_tool.api.binance.client import BinanceClient
from crypto_tax_tool.database.manual_store import count_manual_entries, save_manual_lot, save_manual_price
from crypto_tax_tool.database.sqlite_store import count_balance_rows, count_transactions
from crypto_tax_tool.gui.sync_worker import SyncWorker
from crypto_tax_tool.models.manual_entries import ManualLotEntry, ManualPriceEntry
from crypto_tax_tool.services.config_service import ConfigService
from crypto_tax_tool.services.report_service import ReportGenerationService, ReportValidationError
from crypto_tax_tool.updater import check_for_updates, install_update_from_main


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Crypto Tax Tool")
        self.resize(1050, 900)
        self.sync_thread: QThread | None = None
        self.sync_worker: SyncWorker | None = None
        self.config_service = ConfigService()

        self.status_label = QLabel("Ready. Use read-only API credentials.")
        self.count_label = QLabel(self._local_count_text())

        api_key, api_secret = self.config_service.load_binance_credentials()
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Binance API Key (read-only)")
        self.api_key_input.setText(api_key)
        self.api_secret_input = QLineEdit()
        self.api_secret_input.setPlaceholderText("Binance API Secret")
        self.api_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_secret_input.setText(api_secret)
        self.save_credentials_button = QPushButton("Save Binance API credentials")
        self.save_credentials_button.clicked.connect(self._save_api_credentials)

        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.start_date.setDate(self.start_date.date().addYears(-1))

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        self.end_date.setDate(self.end_date.date().currentDate())

        self.report_number_format = QComboBox()
        self.report_number_format.addItem("German / EU Excel (1.234,56)", "german")
        self.report_number_format.addItem("International / US Excel (1,234.56)", "international")
        self.report_number_format.setCurrentIndex(0)

        self.test_button = QPushButton("Test Binance connection")
        self.test_button.clicked.connect(self._test_binance_connection)

        self.sync_button = QPushButton("Start Binance sync")
        self.sync_button.clicked.connect(self._run_sync)

        self.full_resync_button = QPushButton("Full resync selected date range")
        self.full_resync_button.clicked.connect(self._run_full_resync)

        self.report_button = QPushButton("Create tax report for selected date range")
        self.report_button.clicked.connect(self._create_tax_report)

        self.update_button = QPushButton("Check / install update")
        self.update_button.clicked.connect(self._check_for_updates)

        self.refresh_button = QPushButton("Refresh local counts")
        self.refresh_button.clicked.connect(self._refresh_count)

        self.manual_price_asset = QLineEdit()
        self.manual_price_asset.setPlaceholderText("Asset, e.g. BTC")
        self.manual_price_date = QDateEdit()
        self.manual_price_date.setCalendarPopup(True)
        self.manual_price_date.setDisplayFormat("yyyy-MM-dd")
        self.manual_price_date.setDate(self.manual_price_date.date().currentDate())
        self.manual_price_value = QDoubleSpinBox()
        self.manual_price_value.setMaximum(1_000_000_000)
        self.manual_price_value.setDecimals(8)
        self.manual_price_reason = QLineEdit()
        self.manual_price_reason.setPlaceholderText("Reason/source")
        self.manual_price_button = QPushButton("Save manual EUR price")
        self.manual_price_button.clicked.connect(self._save_manual_price)

        self.manual_lot_asset = QLineEdit()
        self.manual_lot_asset.setPlaceholderText("Asset, e.g. BTC")
        self.manual_lot_date = QDateEdit()
        self.manual_lot_date.setCalendarPopup(True)
        self.manual_lot_date.setDisplayFormat("yyyy-MM-dd")
        self.manual_lot_date.setDate(self.manual_lot_date.date().currentDate())
        self.manual_lot_quantity = QDoubleSpinBox()
        self.manual_lot_quantity.setMaximum(1_000_000_000)
        self.manual_lot_quantity.setDecimals(12)
        self.manual_lot_cost = QDoubleSpinBox()
        self.manual_lot_cost.setMaximum(1_000_000_000)
        self.manual_lot_cost.setDecimals(2)
        self.manual_lot_reference = QLineEdit()
        self.manual_lot_reference.setPlaceholderText("Source/reference")
        self.manual_lot_reason = QLineEdit()
        self.manual_lot_reason.setPlaceholderText("Reason")
        self.manual_lot_button = QPushButton("Save manual FIFO lot")
        self.manual_lot_button.clicked.connect(self._save_manual_lot)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Crypto Tax Tool"))
        layout.addWidget(self.status_label)
        layout.addWidget(self.count_label)

        layout.addWidget(QLabel("Binance API credentials"))
        api_row = QHBoxLayout()
        api_row.addWidget(self.api_key_input)
        api_row.addWidget(self.api_secret_input)
        api_row.addWidget(self.save_credentials_button)
        layout.addLayout(api_row)
        layout.addWidget(QLabel("Important: create the Binance key with read-only permissions only. Do not enable trading or withdrawals."))

        layout.addWidget(QLabel("Sync / report start date"))
        layout.addWidget(self.start_date)
        layout.addWidget(QLabel("Sync / report end date"))
        layout.addWidget(self.end_date)
        layout.addWidget(QLabel("Report number/date format"))
        layout.addWidget(self.report_number_format)
        layout.addWidget(self.test_button)
        layout.addWidget(self.sync_button)
        layout.addWidget(self.full_resync_button)
        layout.addWidget(self.report_button)
        layout.addWidget(self.update_button)
        layout.addWidget(self.refresh_button)

        layout.addWidget(QLabel("Manual EUR price"))
        price_row = QHBoxLayout()
        price_row.addWidget(self.manual_price_asset)
        price_row.addWidget(self.manual_price_date)
        price_row.addWidget(self.manual_price_value)
        price_row.addWidget(self.manual_price_reason)
        price_row.addWidget(self.manual_price_button)
        layout.addLayout(price_row)

        layout.addWidget(QLabel("Manual FIFO lot / external acquisition"))
        lot_row = QHBoxLayout()
        lot_row.addWidget(self.manual_lot_asset)
        lot_row.addWidget(self.manual_lot_date)
        lot_row.addWidget(self.manual_lot_quantity)
        lot_row.addWidget(self.manual_lot_cost)
        lot_row.addWidget(self.manual_lot_reference)
        lot_row.addWidget(self.manual_lot_reason)
        lot_row.addWidget(self.manual_lot_button)
        layout.addLayout(lot_row)

        layout.addWidget(QLabel("Status log"))
        layout.addWidget(self.log_box)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def _local_count_text(self) -> str:
        return (
            f"Local transactions: {count_transactions()} | Balance rows: {count_balance_rows()} | "
            f"Manual entries: {count_manual_entries()}"
        )

    def _refresh_count(self) -> None:
        self.count_label.setText(self._local_count_text())

    def _append_log(self, message: str) -> None:
        self.log_box.append(message)

    def _selected_start_end(self) -> tuple[datetime, datetime]:
        start = datetime.combine(self.start_date.date().toPython(), datetime.min.time())
        end = datetime.combine(self.end_date.date().toPython(), datetime.max.time())
        return start, end

    def _selected_number_format(self) -> str:
        return str(self.report_number_format.currentData() or "international")

    def _save_api_credentials(self) -> None:
        try:
            path = self.config_service.save_binance_credentials(
                self.api_key_input.text(),
                self.api_secret_input.text(),
            )
        except Exception as exc:  # noqa: BLE001
            self.status_label.setText(f"Could not save API credentials: {exc}")
            self._append_log(f"Could not save API credentials: {exc}")
        else:
            self.status_label.setText("Binance API credentials saved.")
            self._append_log(f"Binance API credentials saved to {path}.")

    def _test_binance_connection(self) -> None:
        try:
            BinanceClient().test_connection()
        except Exception as exc:  # noqa: BLE001
            self.status_label.setText(f"Connection failed: {exc}")
            self._append_log(f"Connection failed: {exc}")
        else:
            self.status_label.setText("Binance API is reachable.")
            self._append_log("Binance API is reachable.")

    def _check_for_updates(self) -> None:
        self.update_button.setEnabled(False)
        self.status_label.setText("Checking for updates.")
        try:
            info = check_for_updates()
            self._append_log(info.message)
            if info.release_url:
                self._append_log(f"Update reference: {info.release_url}")

            if not info.update_available:
                self.status_label.setText("No update available.")
                return

            self.status_label.setText("Installing update.")
            self._append_log("Installing update automatically...")
            result = install_update_from_main(progress_callback=self._append_log)
            self._append_log(result.message)
            if result.success:
                self.status_label.setText("Update installed. Restart required.")
                self._append_log("Update installed. Please close and restart the tool.")
                self._append_log("If you use the Windows EXE, run build_windows.bat once after closing the tool.")
            else:
                self.status_label.setText("Update installation failed.")
        except Exception as exc:  # noqa: BLE001
            self.status_label.setText("Update failed.")
            self._append_log(f"Update failed: {type(exc).__name__}: {exc}")
        finally:
            self.update_button.setEnabled(True)

    def _create_tax_report(self) -> None:
        report_start, report_end = self._selected_start_end()
        number_format = self._selected_number_format()
        self.status_label.setText("Creating tax report.")
        self.report_button.setEnabled(False)
        try:
            result = ReportGenerationService().generate_tax_report(
                report_start=report_start,
                report_end=report_end,
                number_format=number_format,
            )
        except ReportValidationError as exc:
            self.status_label.setText("Report validation failed.")
            self._append_log("Report validation failed:")
            for issue in exc.validation_report.errors:
                self._append_log(f"ERROR {issue.code}: {issue.message}")
        except Exception as exc:  # noqa: BLE001
            self.status_label.setText(f"Report failed: {exc}")
            self._append_log(f"Report failed: {exc}")
        else:
            missing_count = getattr(result, "missing_inventory_issues", 0)
            if missing_count:
                self.status_label.setText(f"Report created with {missing_count} missing inventory issue(s).")
            else:
                self.status_label.setText("Report created.")
            income_count = getattr(result, "income_events", 0)
            self._append_log(
                f"Report created for {report_start.date()} to {report_end.date()}: {result.output_dir} | "
                f"number format: {number_format}, transactions: {result.transactions}, disposals: {result.disposals}, "
                f"income events: {income_count}, open lots: {result.open_lots}, manual lots: {result.manual_lots}, "
                f"missing inventory issues: {missing_count}"
            )
            if missing_count:
                self._append_log(f"Missing inventory details: {result.missing_inventory_csv}")
                self._append_log("Review the Missing Inventory Excel sheet or CSV. Add manual FIFO lots for material amounts.")
            if result.backup_path:
                self._append_log(f"Backup before report: {result.backup_path}")
            for issue in result.validation_report.warnings:
                self._append_log(f"WARNING {issue.code}: {issue.message}")
        finally:
            self.report_button.setEnabled(True)

    def _save_manual_price(self) -> None:
        try:
            timestamp = datetime.combine(self.manual_price_date.date().toPython(), datetime.min.time())
            entry = ManualPriceEntry(
                asset=self.manual_price_asset.text().strip().upper(),
                quote_asset="EUR",
                timestamp=timestamp,
                price=Decimal(str(self.manual_price_value.value())),
                reason=self.manual_price_reason.text().strip() or "Manual price entry",
            )
            save_manual_price(entry)
        except Exception as exc:  # noqa: BLE001
            self._append_log(f"Manual price failed: {exc}")
        else:
            self._append_log(f"Manual price saved: {entry.asset}/EUR {entry.price} at {entry.timestamp.date()}")
            self._refresh_count()

    def _save_manual_lot(self) -> None:
        try:
            acquired_at = datetime.combine(self.manual_lot_date.date().toPython(), datetime.min.time())
            entry = ManualLotEntry(
                asset=self.manual_lot_asset.text().strip().upper(),
                acquired_at=acquired_at,
                quantity=Decimal(str(self.manual_lot_quantity.value())),
                cost_basis_eur=Decimal(str(self.manual_lot_cost.value())),
                reason=self.manual_lot_reason.text().strip() or "Manual external acquisition",
                source_reference=self.manual_lot_reference.text().strip() or None,
            )
            save_manual_lot(entry)
        except Exception as exc:  # noqa: BLE001
            self._append_log(f"Manual lot failed: {exc}")
        else:
            self._append_log(
                f"Manual lot saved: {entry.quantity} {entry.asset}, cost basis EUR {entry.cost_basis_eur}"
            )
            self._refresh_count()

    def _run_sync(self) -> None:
        self._start_sync(full_resync=False)

    def _run_full_resync(self) -> None:
        self._start_sync(full_resync=True)

    def _start_sync(self, full_resync: bool) -> None:
        start, end = self._selected_start_end()
        if full_resync:
            self.status_label.setText("Full resync running in background.")
            self._append_log(
                f"Starting FULL resync from {start.isoformat()} to {end.isoformat()} "
                "(ignoring incremental sync state)"
            )
        else:
            self.status_label.setText("Sync running in background.")
            self._append_log(f"Starting sync from {start.isoformat()} to {end.isoformat()}")
        self.sync_button.setEnabled(False)
        self.full_resync_button.setEnabled(False)

        self.sync_thread = QThread()
        self.sync_worker = SyncWorker(start=start, end=end, full_resync=full_resync)
        self.sync_worker.moveToThread(self.sync_thread)
        self.sync_thread.started.connect(self.sync_worker.run)
        self.sync_worker.log.connect(self._append_log)
        self.sync_worker.finished.connect(self._sync_finished)
        self.sync_worker.failed.connect(self._sync_failed)
        self.sync_worker.finished.connect(self.sync_thread.quit)
        self.sync_worker.failed.connect(self.sync_thread.quit)
        self.sync_thread.finished.connect(self.sync_thread.deleteLater)
        self.sync_thread.start()

    def _sync_finished(self, summary) -> None:
        self.status_label.setText("Sync finished.")
        self._append_log(
            f"Sync finished: {summary.inserted} transactions, {summary.balance_rows} balance rows."
        )
        self._refresh_count()
        self.sync_button.setEnabled(True)
        self.full_resync_button.setEnabled(True)

    def _sync_failed(self, message: str) -> None:
        self.status_label.setText(f"Sync failed: {message}")
        self._append_log(f"Sync failed: {message}")
        self.sync_button.setEnabled(True)
        self.full_resync_button.setEnabled(True)
