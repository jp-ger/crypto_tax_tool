import logging
from logging.handlers import RotatingFileHandler

from crypto_tax_tool.settings import get_settings


def configure_logging() -> None:
    """Configure console and rotating file logging."""
    settings = get_settings()
    settings.log_dir.mkdir(parents=True, exist_ok=True)

    log_format = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))

    file_handler = RotatingFileHandler(
        settings.log_dir / "crypto_tax_tool.log",
        maxBytes=5_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(log_format))

    root.addHandler(console_handler)
    root.addHandler(file_handler)
