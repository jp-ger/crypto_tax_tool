from datetime import UTC, datetime
from decimal import Decimal

from crypto_tax_tool.database.manual_store import (
    count_manual_change_log,
    count_manual_entries,
    get_manual_price,
    load_manual_lots,
    save_manual_lot,
    save_manual_price,
)
from crypto_tax_tool.database.sqlite_store import initialize_sqlite
from crypto_tax_tool.models.manual_entries import ManualLotEntry, ManualPriceEntry
from crypto_tax_tool.services.pricing import HistoricalPriceService, StaticPriceProvider


def _prepare_db(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CRYPTO_TAX_DB_PATH", str(tmp_path / "test.sqlite3"))

    from crypto_tax_tool.settings import get_settings

    get_settings.cache_clear()
    initialize_sqlite()


def test_manual_price_entry_overrides_provider(tmp_path, monkeypatch) -> None:
    _prepare_db(tmp_path, monkeypatch)
    timestamp = datetime(2025, 1, 1, tzinfo=UTC)
    entry = ManualPriceEntry(
        asset="ABC",
        quote_asset="EUR",
        timestamp=timestamp,
        price=Decimal("12.34"),
        reason="Missing historical exchange price.",
    )

    assert save_manual_price(entry) is True
    manual = get_manual_price("ABC", "EUR", timestamp)
    assert manual is not None
    assert manual.price == Decimal("12.34")

    service = HistoricalPriceService(
        providers=[StaticPriceProvider({("ABC", "EUR"): Decimal("99")})]
    )
    assert service.get_price("ABC", "EUR", timestamp).price == Decimal("12.34")
    assert count_manual_entries() == 1
    assert count_manual_change_log() == 1


def test_manual_lot_entry_is_audited_and_loadable(tmp_path, monkeypatch) -> None:
    _prepare_db(tmp_path, monkeypatch)
    entry = ManualLotEntry(
        asset="BTC",
        acquired_at=datetime(2021, 1, 1, tzinfo=UTC),
        quantity=Decimal("0.5"),
        cost_basis_eur=Decimal("15000"),
        reason="External purchase before Binance deposit.",
        source_reference="Kraken CSV 2021",
    )

    assert save_manual_lot(entry) is True
    assert count_manual_entries() == 1
    assert count_manual_change_log() == 1

    lots = load_manual_lots()
    assert len(lots) == 1
    assert lots[0].asset == "BTC"
    assert lots[0].quantity == Decimal("0.5")
    assert lots[0].cost_basis_eur == Decimal("15000")
    assert lots[0].source_transaction_id == "Kraken CSV 2021"
