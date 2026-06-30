from datetime import UTC, datetime
from decimal import Decimal

from crypto_tax_tool.database.sqlite_store import count_prices, initialize_sqlite
from crypto_tax_tool.services.pricing import HistoricalPriceService, StaticPriceProvider


def test_price_service_uses_provider_and_cache(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CRYPTO_TAX_DB_PATH", str(tmp_path / "test.sqlite3"))

    from crypto_tax_tool.settings import get_settings

    get_settings.cache_clear()
    initialize_sqlite()

    service = HistoricalPriceService(
        providers=[StaticPriceProvider({("BTC", "EUR"): Decimal("90000")})]
    )
    timestamp = datetime(2025, 1, 1, tzinfo=UTC)

    first = service.get_price("BTC", "EUR", timestamp)
    second = service.get_price("BTC", "EUR", timestamp)

    assert first.price == Decimal("90000")
    assert second.price == Decimal("90000")
    assert count_prices() == 1
