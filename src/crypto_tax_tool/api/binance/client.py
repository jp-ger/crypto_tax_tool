import hashlib
import hmac
import time
from datetime import UTC, datetime
from urllib.parse import urlencode

import requests

from crypto_tax_tool.api.binance.normalizers import normalize_spot_trade
from crypto_tax_tool.api.binance.spot_sync import split_into_daily_windows
from crypto_tax_tool.api.binance.symbols import BinanceSymbol, parse_exchange_info
from crypto_tax_tool.api.exchange_base import ExchangeClient
from crypto_tax_tool.models.transactions import NormalizedTransaction
from crypto_tax_tool.settings import get_settings


def _to_millis(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return int(value.timestamp() * 1000)


class BinanceClient(ExchangeClient):
    """Small Binance REST client. Product-specific sync methods will be added iteratively."""

    base_url = "https://api.binance.com"

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.binance_api_key
        self.api_secret = settings.binance_api_secret.encode("utf-8")
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({"X-MBX-APIKEY": self.api_key})

    def test_connection(self) -> bool:
        response = self.session.get(f"{self.base_url}/api/v3/ping", timeout=15)
        response.raise_for_status()
        return True

    def get_exchange_symbols(self) -> list[BinanceSymbol]:
        response = self.session.get(f"{self.base_url}/api/v3/exchangeInfo", timeout=30)
        response.raise_for_status()
        return parse_exchange_info(response.json())

    def sync_transactions(self, start: datetime, end: datetime) -> list[NormalizedTransaction]:
        records: list[NormalizedTransaction] = []
        for item in self.get_exchange_symbols():
            if item.status != "TRADING":
                continue
            records.extend(self.get_spot_trades(item, start, end))
        return records

    def get_spot_trades(
        self, symbol: BinanceSymbol, start: datetime, end: datetime
    ) -> list[NormalizedTransaction]:
        records: list[NormalizedTransaction] = []
        for window in split_into_daily_windows(start, end):
            rows = self._signed_get(
                "/api/v3/myTrades",
                {
                    "symbol": symbol.symbol,
                    "startTime": _to_millis(window.start),
                    "endTime": _to_millis(window.end),
                    "limit": 1000,
                },
            )
            if not isinstance(rows, list):
                continue
            for row in rows:
                row["symbol"] = symbol.symbol
                records.append(normalize_spot_trade(row, symbol.base_asset, symbol.quote_asset))
        return records

    def _signed_get(self, path: str, params: dict[str, object] | None = None) -> dict | list:
        if not self.api_key or not self.api_secret:
            raise ValueError("Binance API key and secret are required for signed endpoints.")
        payload = dict(params or {})
        payload["timestamp"] = int(time.time() * 1000)
        query = urlencode(payload)
        signature = hmac.new(self.api_secret, query.encode("utf-8"), hashlib.sha256).hexdigest()
        url = f"{self.base_url}{path}?{query}&signature={signature}"
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
