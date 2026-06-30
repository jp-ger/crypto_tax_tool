from datetime import UTC, datetime
from decimal import Decimal

from crypto_tax_tool.services.binance_price_provider import BinanceHistoricalPriceProvider


def test_eur_stablecoin_price_is_one() -> None:
    provider = BinanceHistoricalPriceProvider()
    price = provider.get_price("EUR", "EUR", datetime(2025, 1, 1, tzinfo=UTC))

    assert price is not None
    assert price.price == Decimal("1")
    assert price.provider == "stablecoin_fallback"


def test_usd_stablecoin_uses_eurusdt_inverse(monkeypatch) -> None:
    provider = BinanceHistoricalPriceProvider()

    def fake_symbol_price(base, quote, timestamp):
        if base == "EUR" and quote == "USDT":
            from crypto_tax_tool.models.prices import HistoricalPrice

            return HistoricalPrice(
                asset="EUR",
                quote_asset="USDT",
                timestamp=timestamp,
                price=Decimal("1.25"),
                provider="binance",
                pair="EURUSDT",
            )
        return None

    monkeypatch.setattr(provider, "_get_symbol_price", fake_symbol_price)
    price = provider.get_price("USDC", "EUR", datetime(2025, 1, 1, tzinfo=UTC))

    assert price is not None
    assert price.price == Decimal("0.8")


def test_crypto_usdt_price_converts_to_eur(monkeypatch) -> None:
    provider = BinanceHistoricalPriceProvider()

    def fake_symbol_price(base, quote, timestamp):
        from crypto_tax_tool.models.prices import HistoricalPrice

        if base == "BTC" and quote == "USDT":
            return HistoricalPrice(
                asset="BTC",
                quote_asset="USDT",
                timestamp=timestamp,
                price=Decimal("100000"),
                provider="binance",
                pair="BTCUSDT",
            )
        if base == "EUR" and quote == "USDT":
            return HistoricalPrice(
                asset="EUR",
                quote_asset="USDT",
                timestamp=timestamp,
                price=Decimal("1.25"),
                provider="binance",
                pair="EURUSDT",
            )
        return None

    monkeypatch.setattr(provider, "_get_symbol_price", fake_symbol_price)
    price = provider.get_price("BTC", "EUR", datetime(2025, 1, 1, tzinfo=UTC))

    assert price is not None
    assert price.price == Decimal("80000")
