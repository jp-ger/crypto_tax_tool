import sys

from PySide6.QtWidgets import QApplication

from crypto_tax_tool.gui.main_window import MainWindow
from crypto_tax_tool.utils.logging import configure_logging


def main() -> int:
    configure_logging()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
