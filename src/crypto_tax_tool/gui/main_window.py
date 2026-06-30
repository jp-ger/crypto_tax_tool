from PySide6.QtWidgets import QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget

from crypto_tax_tool.api.binance.client import BinanceClient


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Crypto Tax Tool")
        self.resize(900, 600)

        self.status_label = QLabel("Ready. Use read-only API credentials.")
        self.test_button = QPushButton("Test Binance connection")
        self.test_button.clicked.connect(self._test_binance_connection)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Crypto Tax Tool"))
        layout.addWidget(self.status_label)
        layout.addWidget(self.test_button)
        layout.addStretch()

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def _test_binance_connection(self) -> None:
        try:
            BinanceClient().test_connection()
        except Exception as exc:  # noqa: BLE001
            self.status_label.setText(f"Connection failed: {exc}")
        else:
            self.status_label.setText("Binance API is reachable.")
