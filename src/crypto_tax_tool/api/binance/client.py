import hashlib
import hmac
import time
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import urlencode

import requests

from crypto_tax_tool.api.binance.http import with_retries
from crypto_tax_tool.api.binance.normalizers import (
    normalize_account_balances,
    normalize_convert_trade,
    normalize_reward,
    normalize_spot_trade,
    normalize_transfer,
)
from crypto_tax_tool.api.binance.pagination import extract_rows, paginate_numbered
from crypto_tax_tool.api.binance.spot_sync import split_into_daily_windows
from crypto_tax_tool.api.binance.symbols import BinanceSymbol, parse_exchange_info
from crypto_tax_tool.api.exchange_base import ExchangeClient
from crypto_tax_tool.models.balances import BalanceSnapshot
from crypto_tax_tool.models.transactions import NormalizedTransaction
from crypto_tax_tool.settings import get_settings


BINANCE_SPOT_HISTORY_START = datetime(2017, 7, 14)


def _to_millis(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return int(value.timestamp() * 1000)


def _row_time_millis(row: dict) -> int:
    return int(row.get("time") or row.get("insertTime") or row.get("timestamp") or 0)


class BinanceClient(ExchangeClient):
    """Binance REST client with product-specific synchronization loaders."""

    base_url = "https://api.binance.com"

    def __init__(self, progress_callback: Callable[[str], None] | None = None) -> None:
        settings = get_settings()
        self.api_key = settings.binance_api_key
        self.api_secret = settings.binance_api_secret.encode("utf-8")
        self.progress_callback = progress_callback
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({"X-MBX-APIKEY": self.api_key})

    def _log(self, message: str) -> None:
        if self.progress_callback:
            self.progress_callback(message)

    def test_connection(self) -> bool:
        response = with_retries(lambda: self.session.get(f"{self.base_url}/api/v3/ping", timeout=15))
        response.raise_for_status()
        return True

    def get_exchange_symbols(self) -> list[BinanceSymbol]:
        self._log("Loading Binance exchange symbols...")
        response = with_retries(
            lambda: self.session.get(f"{self.base_url}/api/v3/exchangeInfo", timeout=30)
        )
        symbols = parse_exchange_info(response.json())
        self._log(f"Loaded {len(symbols)} Binance exchange symbols.")
        return symbols

    def get_account_snapshot(self) -> BalanceSnapshot:
        self._log("Requesting Binance account snapshot...")
        payload = self._signed_get("/api/v3/account")
        if not isinstance(payload, dict):
            raise ValueError("Unexpected account payload from Binance API.")
        return normalize_account_balances(payload)

    def sync_transactions(self, start: datetime, end: datetime) -> list[NormalizedTransaction]:
        if start < BINANCE_SPOT_HISTORY_START:
            self._log(
                f"Start date {start.date()} is before Binance spot history. "
                f"Using {BINANCE_SPOT_HISTORY_START.date()} for API sync."
            )
            start = BINANCE_SPOT_HISTORY_START

        self._log(f"Binance transaction sync range: {start.isoformat()} to {end.isoformat()}")
        records: list[NormalizedTransaction] = []

        self._log("Syncing spot trades...")
        spot_records = self.sync_spot_trades(start, end)
        records.extend(spot_records)
        self._log(f"Spot trades synced: {len(spot_records)} rows.")

        self._log("Syncing convert trades...")
        convert_records = self.sync_convert_trades(start, end)
        records.extend(convert_records)
        self._log(f"Convert trades synced: {len(convert_records)} rows.")

        self._log("Syncing asset rewards/dividends...")
        asset_reward_records = self.sync_asset_rewards(start, end)
        records.extend(asset_reward_records)
        self._log(f"Asset rewards/dividends synced: {len(asset_reward_records)} rows.")

        self._log("Syncing Simple Earn rewards...")
        simple_earn_records = self.sync_simple_earn_rewards(start, end)
        records.extend(simple_earn_records)
        self._log(f"Simple Earn rewards synced: {len(simple_earn_records)} rows.")

        self._log("Syncing deposits and withdrawals...")
        transfer_records = self.sync_transfers(start, end)
        records.extend(transfer_records)
        self._log(f"Deposits and withdrawals synced: {len(transfer_records)} rows.")

        self._log(f"All Binance transaction loaders completed. Total rows: {len(records)}.")
        return records

    def sync_spot_trades(self, start: datetime, end: datetime) -> list[NormalizedTransaction]:
        records: list[NormalizedTransaction] = []
        symbols = [item for item in self.get_exchange_symbols() if item.status == "TRADING"]
        self._log(
            f"Checking spot trades for {len(symbols)} active trading symbols. "
            "First detecting symbols with account trades, then using daily windows only for those symbols."
        )

        traded_symbols: list[BinanceSymbol] = []
        for index, item in enumerate(symbols, start=1):
            if index == 1 or index % 50 == 0 or index == len(symbols):
                self._log(f"Detecting traded symbols: {index}/{len(symbols)} ({item.symbol})")
            if self._symbol_has_any_trades(item):
                traded_symbols.append(item)
                self._log(f"Detected account trade history for {item.symbol}.")

        self._log(f"Detected {len(traded_symbols)} symbols with account spot trades.")
        for index, item in enumerate(traded_symbols, start=1):
            self._log(f"Importing spot trades for symbol {index}/{len(traded_symbols)} ({item.symbol})")
            symbol_records = self.get_spot_trades(item, start, end)
            self._log(f"Imported {len(symbol_records)} spot trade rows for {item.symbol}.")
            records.extend(symbol_records)
        return records

    def _symbol_has_any_trades(self, symbol: BinanceSymbol) -> bool:
        rows = self._signed_get(
            "/api/v3/myTrades",
            {
                "symbol": symbol.symbol,
                "limit": 1,
            },
        )
        return isinstance(rows, list) and len(rows) > 0

    def get_spot_trades(
        self, symbol: BinanceSymbol, start: datetime, end: datetime
    ) -> list[NormalizedTransaction]:
        records: list[NormalizedTransaction] = []
        windows = split_into_daily_windows(start, end)
        for window_index, window in enumerate(windows, start=1):
            if window_index == 1 or window_index % 90 == 0 or window_index == len(windows):
                self._log(f"{symbol.symbol}: daily window {window_index}/{len(windows)}")
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
                if not isinstance(row, dict):
                    continue
                row["symbol"] = symbol.symbol
                records.append(normalize_spot_trade(row, symbol.base_asset, symbol.quote_asset))
            if rows:
                self._log(f"{symbol.symbol}: found {len(rows)} raw trade rows in current window.")
        return records

    def sync_convert_trades(self, start: datetime, end: datetime) -> list[NormalizedTransaction]:
        records: list[NormalizedTransaction] = []
        windows = split_into_daily_windows(start, end)
        for window_index, window in enumerate(windows, start=1):
            if window_index == 1 or window_index % 30 == 0 or window_index == len(windows):
                self._log(f"Convert trade progress: window {window_index}/{len(windows)}")
            rows = paginate_numbered(
                lambda page: self._signed_get(
                    "/sapi/v1/convert/tradeFlow",
                    {
                        "startTime": _to_millis(window.start),
                        "endTime": _to_millis(window.end),
                        "limit": 1000,
                        "current": page,
                    },
                ),
                rows_key="list",
                page_size=1000,
            )
            for row in rows:
                records.extend(normalize_convert_trade(row))
        return records

    def sync_asset_rewards(self, start: datetime, end: datetime) -> list[NormalizedTransaction]:
        records: list[NormalizedTransaction] = []
        windows = split_into_daily_windows(start, end)
        for window_index, window in enumerate(windows, start=1):
            if window_index == 1 or window_index % 30 == 0 or window_index == len(windows):
                self._log(f"Asset reward progress: window {window_index}/{len(windows)}")
            rows = paginate_numbered(
                lambda page: self._signed_get(
                    "/sapi/v1/asset/assetDividend",
                    {
                        "startTime": _to_millis(window.start),
                        "endTime": _to_millis(window.end),
                        "limit": 500,
                        "current": page,
                    },
                ),
                rows_key="rows",
                page_size=500,
            )
            for row in rows:
                records.append(normalize_reward(row, product="asset_dividend", id_prefix="assetDividend"))
        return records

    def sync_simple_earn_rewards(self, start: datetime, end: datetime) -> list[NormalizedTransaction]:
        records: list[NormalizedTransaction] = []
        endpoints = [
            ("/sapi/v1/simple-earn/flexible/history/rewardsRecord", "simple_earn_flexible"),
            ("/sapi/v1/simple-earn/locked/history/rewardsRecord", "simple_earn_locked"),
        ]
        windows = split_into_daily_windows(start, end)
        for path, product in endpoints:
            self._log(f"Simple Earn endpoint: {product}")
            for window_index, window in enumerate(windows, start=1):
                if window_index == 1 or window_index % 30 == 0 or window_index == len(windows):
                    self._log(f"{product} progress: window {window_index}/{len(windows)}")
                rows = paginate_numbered(
                    lambda page: self._signed_get(
                        path,
                        {
                            "startTime": _to_millis(window.start),
                            "endTime": _to_millis(window.end),
                            "current": page,
                            "size": 100,
                        },
                    ),
                    rows_key="rows",
                    page_size=100,
                )
                for row in rows:
                    records.append(normalize_reward(row, product=product, id_prefix=product))
        return records

    def sync_transfers(self, start: datetime, end: datetime) -> list[NormalizedTransaction]:
        records: list[NormalizedTransaction] = []
        windows = split_into_daily_windows(start, end)
        for window_index, window in enumerate(windows, start=1):
            if window_index == 1 or window_index % 30 == 0 or window_index == len(windows):
                self._log(f"Transfer progress: window {window_index}/{len(windows)}")
            deposits = self._signed_get(
                "/sapi/v1/capital/deposit/hisrec",
                {"startTime": _to_millis(window.start), "endTime": _to_millis(window.end)},
            )
            for row in extract_rows(deposits):
                records.append(normalize_transfer(row, "deposit", "deposit", True))

            withdrawals = self._signed_get(
                "/sapi/v1/capital/withdraw/history",
                {"startTime": _to_millis(window.start), "endTime": _to_millis(window.end)},
            )
            for row in extract_rows(withdrawals):
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
        response.raise_for_status()
        return response.json()
