from datetime import datetime, timedelta
from decimal import Decimal

import requests

from crypto_tax_tool.api.binance.http import with_retries
from crypto_tax_tool.models.prices import HistoricalPrice
from crypto_tax_tool.services.pricing import PriceProvider


STABLECOIN_EUR_FALLBACKS = {"EUR": Decimal("1"), "EURC": Decimal("1")}
USD_STABLECOINS = {"USDC", "USDT", "BUSD", "FDUSD", "TUSD", "DAI"}


class BinanceHistoricalPriceProvider(PriceProvider):
    provider_name = "binance"
    base_url = "https://api.binance.com"

    def __init__(self) -> None:
        self.session = requests.Session()

    def get_price(self, asset: str, quote_asset: str, timestamp: datetime) -> HistoricalPrice | None:
        asset = asset.upper()
        quote_asset = quote_asset.upper()
        if asset in STABLECOIN_EUR_FALLBACKS and quote_asset == "EUR":
            return HistoricalPrice(
                asset=asset,
                quote_asset=quote_asset,
                timestamp=timestamp,
                price=STABLECOIN_EUR_FALLBACKS[asset],
                provider="stablecoin_fallback",
                pair=f"{asset}{quote_asset}",
            )

        direct = self._get_symbol_price(asset, quote_asset, timestamp)
        if direct:
            return direct

        if quote_asset == "EUR" and asset in USD_STABLECOINS:
            eurusd = self._get_symbol_price("EUR", "USDT", timestamp)
            if eurusd and eurusd.price != 0:
                return HistoricalPrice(
                    asset=asset,
                    quote_asset=quote_asset,
                    timestamp=timestamp,
                    price=Decimal("1") / eurusd.price,
                    provider=self.provider_name,
                    pair=f"EURUSDT_inverse_for_{asset}EUR",
                )

        if quote_asset == "EUR":
            usdt_price = self._get_symbol_price(asset, "USDT", timestamp)
            eurusdt = self._get_symbol_price("EUR", "USDT", timestamp)
            if usdt_price and eurusdt and eurusdt.price != 0:
                return HistoricalPrice(
                    asset=asset,
                    quote_asset=quote_asset,
                    timestamp=timestamp,
                    price=usdt_price.price / eurusdt.price,
                    provider=self.provider_name,
                    pair=f"{asset}USDT/EURUSDT",
                )
        return None

    def _get_symbol_price(self, base: str, quote: str, timestamp: datetime) -> HistoricalPrice | None:
        symbol = f"{base}{quote}"
        start_ms = int(timestamp.timestamp() * 1000)
        end_ms = int((timestamp + timedelta(hours=1)).timestamp() * 1000)
        response = with_retries(
            lambda: self.session.get(
                f"{self.base_url}/api/v3/klines",
                params={
                    "symbol": symbol,
                    "interval": "1h",
                    "startTime": start_ms,
                    "endTime": end_ms,
                    "limit": 1,
                },
                timeout=20,
            )
        )
        rows = response.json()
        if not isinstance(rows, list) or not rows:
            return None
        close_price = Decimal(str(rows[0][4]))
        return HistoricalPrice(
            asset=base,
            quote_asset=quote,
            timestamp=timestamp,
            price=close_price,
            provider=self.provider_name,
            pair=symbol,
        )
