import hashlib
import hmac
import time
from datetime import UTC, datetime
from urllib.parse import urlencode

import requests

from crypto_tax_tool.api.binance.http import with_retries
from crypto_tax_tool.api.binance.normalizers import (
    normalize_convert_trade,
    normalize_reward,
    normalize_spot_trade,
    normalize_transfer,
)
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
    """Binance REST client with product-specific synchronization loaders."""

    base_url = "https://api.binance.com"

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.binance_api_key
        self.api_secret = settings.binance_api_secret.encode("utf-8")
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({"X-MBX-APIKEY": self.api_key})

    def test_connection(self) -> bool:
        response = with_retries(lambda: self.session.get(f"{self.base_url}/api/v3/ping", timeout=15))
        response.raise_for_status()
        return True

    def get_exchange_symbols(self) -> list[BinanceSymbol]:
        response = with_retries(
            lambda: self.session.get(f"{self.base_url}/api/v3/exchangeInfo", timeout=30)
        )
        return parse_exchange_info(response.json())

    def sync_transactions(self, start: datetime, end: datetime) -> list[NormalizedTransaction]:
        records: list[NormalizedTransaction] = []
        records.extend(self.sync_spot_trades(start, end))
        records.extend(self.sync_convert_trades(start, end))
        records.extend(self.sync_asset_rewards(start, end))
        records.extend(self.sync_simple_earn_rewards(start, end))
        records.extend(self.sync_transfers(start, end))
        return records

    def sync_spot_trades(self, start: datetime, end: datetime) -> list[NormalizedTransaction]:
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

    def sync_convert_trades(self, start: datetime, end: datetime) -> list[NormalizedTransaction]:
        records: list[NormalizedTransaction] = []
        for window in split_into_daily_windows(start, end):
            payload = self._signed_get(
                "/sapi/v1/convert/tradeFlow",
                {"startTime": _to_millis(window.start), "endTime": _to_millis(window.end), "limit": 1000},
            )
            rows = payload.get("list", []) if isinstance(payload, dict) else []
            for row in rows:
                records.extend(normalize_convert_trade(row))
        return records

    def sync_asset_rewards(self, start: datetime, end: datetime) -> list[NormalizedTransaction]:
        records: list[NormalizedTransaction] = []
        for window in split_into_daily_windows(start, end):
            payload = self._signed_get(
                "/sapi/v1/asset/assetDividend",
                {"startTime": _to_millis(window.start), "endTime": _to_millis(window.end), "limit": 500},
            )
            rows = payload.get("rows", []) if isinstance(payload, dict) else []
            for row in rows:
                records.append(normalize_reward(row, product="asset_dividend", id_prefix="assetDividend"))
        return records

    def sync_simple_earn_rewards(self, start: datetime, end: datetime) -> list[NormalizedTransaction]:
        records: list[NormalizedTransaction] = []
        endpoints = [
            ("/sapi/v1/simple-earn/flexible/history/rewardsRecord", "simple_earn_flexible"),
            ("/sapi/v1/simple-earn/locked/history/rewardsRecord", "simple_earn_locked"),
        ]
        for path, product in endpoints:
            for window in split_into_daily_windows(start, end):
                payload = self._signed_get(
                    path,
                    {
                        "startTime": _to_millis(window.start),
                        "endTime": _to_millis(window.end),
                        "current": 1,
                        "size": 100,
                    },
                )
                rows = payload.get("rows", []) if isinstance(payload, dict) else []
                for row in rows:
                    records.append(normalize_reward(row, product=product, id_prefix=product))
        return records

    def sync_transfers(self, start: datetime, end: datetime) -> list[NormalizedTransaction]:
        records: list[NormalizedTransaction] = []
        for window in split_into_daily_windows(start, end):
            deposits = self._signed_get(
                "/sapi/v1/capital/deposit/hisrec",
                {"startTime": _to_millis(window.start), "endTime": _to_millis(window.end)},
            )
            if isinstance(deposits, list):
                for row in deposits:
                    records.append(normalize_transfer(row, "deposit", "deposit", True))

            withdrawals = self._signed_get(
                "/sapi/v1/capital/withdraw/history",
                {"startTime": _to_millis(window.start), "endTime": _to_millis(window.end)},
            )
            if isinstance(withdrawals, list):
                for row in withdrawals:
                    records.append(normalize_transfer(row, "withdrawal", "withdrawal", False))
        return records

    def _signed_get(self, path: str, params: dict[str, object] | None = None) -> dict | list:
        if not self.api_key or not self.api_secret:
            raise ValueError("Binance API key and secret are required for signed endpoints.")
        payload = dict(params or {})
        payload["timestamp"] = int(time.time() * 1000)
        query = urlencode(payload)
        signature = hmac.new(self.api_secret, query.encode("utf-8"), hashlib.sha256).hexdigest()
        url = f"{self.base_url}{path}?{query}&signature={signature}"
        response = with_retries(lambda: self.session.get(url, timeout=30))
        return response.json()
