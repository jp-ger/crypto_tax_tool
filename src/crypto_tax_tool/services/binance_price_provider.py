from datetime import datetime, timedelta
from decimal import Decimal

import requests

from crypto_tax_tool.api.binance.http import RETRY_STATUS_CODES, with_retries
from crypto_tax_tool.database.sqlite_store import get_sync_state, set_sync_state
from crypto_tax_tool.models.prices import HistoricalPrice
from crypto_tax_tool.services.pricing import PriceProvider


EUR_STABLECOINS = {
    "EUR": Decimal("1"),
    "AEUR": Decimal("1"),
    "EURC": Decimal("1"),
    "EURI": Decimal("1"),
}
USD_STABLECOINS = {"USDC", "USDT", "BUSD", "FDUSD", "TUSD", "DAI", "USDP"}
PRICE_UNAVAILABLE_PREFIX = "binance_price_unavailable"


class BinanceHistoricalPriceProvider(PriceProvider):
    provider_name = "binance"
    base_url = "https://api.binance.com"

    def __init__(self) -> None:
        self.session = requests.Session()

    def get_price(self, asset: str, quote_asset: str, timestamp: datetime) -> HistoricalPrice | None:
        asset = asset.upper()
        quote_asset = quote_asset.upper()
        timestamp = _hour_floor(timestamp)

        if asset == quote_asset:
            return self._price(asset, quote_asset, timestamp, Decimal("1"), "same_asset", asset)

        if quote_asset == "EUR" and asset in EUR_STABLECOINS:
            return self._price(asset, quote_asset, timestamp, EUR_STABLECOINS[asset], "eur_stablecoin", f"{asset}=EUR")

        direct = self._get_symbol_price(asset, quote_asset, timestamp)
        if direct:
            return direct

        inverse = self._get_symbol_price(quote_asset, asset, timestamp)
        if inverse and inverse.price != 0:
            return self._price(
                asset,
                quote_asset,
                timestamp,
                Decimal("1") / inverse.price,
                self.provider_name,
                f"{quote_asset}{asset}_inverse",
            )

        if quote_asset == "EUR" and asset in USD_STABLECOINS:
            return self._usd_stable_to_eur(asset, timestamp)

        if quote_asset == "EUR":
            via_usdt = self._asset_to_eur_via_usdt(asset, timestamp)
            if via_usdt:
                return via_usdt
            via_btc = self._asset_to_eur_via_btc(asset, timestamp)
            if via_btc:
                return via_btc

        return None

    def _usd_stable_to_eur(self, asset: str, timestamp: datetime) -> HistoricalPrice | None:
        eurusdt = self._get_symbol_price("EUR", "USDT", timestamp)
        if eurusdt and eurusdt.price != 0:
            return self._price(
                asset,
                "EUR",
                timestamp,
                Decimal("1") / eurusdt.price,
                self.provider_name,
                f"EURUSDT_inverse_for_{asset}EUR",
            )
        usdteur = self._get_symbol_price("USDT", "EUR", timestamp)
        if usdteur:
            return self._price(asset, "EUR", timestamp, usdteur.price, self.provider_name, f"USDTEUR_for_{asset}EUR")
        return None

    def _asset_to_eur_via_usdt(self, asset: str, timestamp: datetime) -> HistoricalPrice | None:
        usdt_price = self._get_symbol_price(asset, "USDT", timestamp)
        if not usdt_price:
            return None
        eurusdt = self._get_symbol_price("EUR", "USDT", timestamp)
        if eurusdt and eurusdt.price != 0:
            return self._price(
                asset,
                "EUR",
                timestamp,
                usdt_price.price / eurusdt.price,
                self.provider_name,
                f"{asset}USDT/EURUSDT",
            )
        usdteur = self._get_symbol_price("USDT", "EUR", timestamp)
        if usdteur:
            return self._price(
                asset,
                "EUR",
                timestamp,
                usdt_price.price * usdteur.price,
                self.provider_name,
                f"{asset}USDT*USDTEUR",
            )
        return None

    def _asset_to_eur_via_btc(self, asset: str, timestamp: datetime) -> HistoricalPrice | None:
        asset_btc = self._get_symbol_price(asset, "BTC", timestamp)
        btc_eur = self._get_symbol_price("BTC", "EUR", timestamp)
        if asset_btc and btc_eur:
            return self._price(
                asset,
                "EUR",
                timestamp,
                asset_btc.price * btc_eur.price,
                self.provider_name,
                f"{asset}BTC*BTCEUR",
            )
        return None

    def _get_symbol_price(self, base: str, quote: str, timestamp: datetime) -> HistoricalPrice | None:
        symbol = f"{base}{quote}"
        timestamp = _hour_floor(timestamp)
        cache_key = self._unavailable_key(symbol, timestamp)
        if get_sync_state(cache_key):
            return None

        start_ms = int(timestamp.timestamp() * 1000)
        end_ms = int((timestamp + timedelta(hours=1)).timestamp() * 1000)
        response = self._request_klines(symbol=symbol, start_ms=start_ms, end_ms=end_ms)
        if response is None:
            set_sync_state(cache_key, "1")
            return None

        rows = response.json()
        if not isinstance(rows, list) or not rows:
            set_sync_state(cache_key, "1")
            return None
        close_price = Decimal(str(rows[0][4]))
        return self._price(base, quote, timestamp, close_price, self.provider_name, symbol)

    def _request_klines(self, symbol: str, start_ms: int, end_ms: int) -> requests.Response | None:
        params = {
            "symbol": symbol,
            "interval": "1h",
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": 1,
        }
        first_response = self.session.get(f"{self.base_url}/api/v3/klines", params=params, timeout=20)
        if first_response.status_code == 400:
            return None
        if first_response.status_code not in RETRY_STATUS_CODES:
            first_response.raise_for_status()
            return first_response
        return with_retries(
            lambda: self.session.get(f"{self.base_url}/api/v3/klines", params=params, timeout=20)
        )

    def _price(
        self,
        asset: str,
        quote_asset: str,
        timestamp: datetime,
        price: Decimal,
        provider: str,
        pair: str,
    ) -> HistoricalPrice:
        return HistoricalPrice(
            asset=asset,
            quote_asset=quote_asset,
            timestamp=timestamp,
            price=price,
            provider=provider,
            pair=pair,
        )

    def _unavailable_key(self, symbol: str, timestamp: datetime) -> str:
        return f"{PRICE_UNAVAILABLE_PREFIX}:{symbol}:{int(timestamp.timestamp() // 3600)}"


def _hour_floor(value: datetime) -> datetime:
    return value.replace(minute=0, second=0, microsecond=0)
