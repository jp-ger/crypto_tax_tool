import hashlib
import hmac
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
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
from crypto_tax_tool.api.binance.spot_sync import split_into_daily_windows, split_into_monthly_windows
from crypto_tax_tool.api.binance.symbols import BinanceSymbol, parse_exchange_info
from crypto_tax_tool.api.exchange_base import ExchangeClient
from crypto_tax_tool.database.sqlite_store import get_sync_state, set_sync_state
from crypto_tax_tool.models.balances import BalanceSnapshot
from crypto_tax_tool.models.transactions import NormalizedTransaction
from crypto_tax_tool.settings import get_settings


BINANCE_SPOT_HISTORY_START = datetime(2017, 7, 14)
TRADED_SYMBOL_CACHE_KEY = "binance_spot_traded_symbols"
LAST_SYNC_END_KEY = "last_sync_end"
INCREMENTAL_OVERLAP = timedelta(days=1)
EMPTY_WINDOW_PREFIX = "binance_empty_window"
UNAVAILABLE_ENDPOINT_PREFIX = "binance_unavailable_endpoint"
SPOT_MONTHLY_UNSUPPORTED_KEY = "binance_spot_monthly_windows_unsupported"


def _to_millis(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return int(value.timestamp() * 1000)


def _append_if_valid(records: list[NormalizedTransaction], tx: NormalizedTransaction | None) -> None:
    if isinstance(tx, NormalizedTransaction):
        records.append(tx)


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
        response.raise_for_status()
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
        start = self._effective_sync_start(start)
        self._log(f"Binance transaction sync range: {start.isoformat()} to {end.isoformat()}")
        records: list[NormalizedTransaction] = []

        self._log("Syncing deposits and withdrawals first to identify involved assets...")
        transfer_records = self.sync_transfers(start, end)
        records.extend(transfer_records)
        self._log(f"Deposits and withdrawals synced: {len(transfer_records)} rows.")

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

        self._log("Syncing spot trades...")
        spot_records = self.sync_spot_trades(start, end)
        records.extend(spot_records)
        self._log(f"Spot trades synced: {len(spot_records)} rows.")

        self._log(f"All Binance transaction loaders completed. Total rows: {len(records)}.")
        return records

    def _effective_sync_start(self, requested_start: datetime) -> datetime:
        start = max(requested_start, BINANCE_SPOT_HISTORY_START)
        if requested_start < BINANCE_SPOT_HISTORY_START:
            self._log(
                f"Start date {requested_start.date()} is before Binance spot history. "
                f"Using {BINANCE_SPOT_HISTORY_START.date()} for API sync."
            )

        last_sync_end = get_sync_state(LAST_SYNC_END_KEY)
        if not last_sync_end:
            self._log("No previous sync state found. Running initial sync for selected range.")
            return start

        try:
            last_end = datetime.fromisoformat(last_sync_end)
            if last_end.tzinfo is not None:
                last_end = last_end.astimezone(UTC).replace(tzinfo=None)
        except ValueError:
            self._log("Previous sync state could not be parsed. Running selected range.")
            return start

        incremental_start = max(start, last_end - INCREMENTAL_OVERLAP)
        if incremental_start > start:
            self._log(
                "Incremental sync enabled. "
                f"Previous sync ended at {last_end.isoformat()}; starting with 1-day overlap at "
                f"{incremental_start.isoformat()}."
            )
            return incremental_start
        return start

    def sync_spot_trades(self, start: datetime, end: datetime) -> list[NormalizedTransaction]:
        records: list[NormalizedTransaction] = []
        all_symbols = [item for item in self.get_exchange_symbols() if item.status == "TRADING"]
        symbol_by_name = {item.symbol: item for item in all_symbols}
        traded_symbols = self._load_cached_traded_symbols(symbol_by_name)

        if traded_symbols:
            self._log(
                f"Using cached spot symbol list with {len(traded_symbols)} traded symbols. "
                "Skipping full 1350+ symbol detection scan."
            )
        else:
            self._log(
                f"No cached traded-symbol list found. Detecting account trade symbols once across "
                f"{len(all_symbols)} active symbols. Future syncs will reuse this cache."
            )
            traded_symbols = self._detect_traded_symbols(all_symbols)
            self._save_cached_traded_symbols(traded_symbols)

        if not traded_symbols:
            self._log("No account spot trade symbols detected.")
            return records

        if get_sync_state(SPOT_MONTHLY_UNSUPPORTED_KEY):
            windows = split_into_daily_windows(start, end)
            self._log(
                f"Importing spot trades for {len(traded_symbols)} symbols over {len(windows)} daily windows "
                "because Binance rejected larger spot trade windows earlier."
            )
        else:
            windows = split_into_monthly_windows(start, end)
            self._log(
                f"Importing spot trades for {len(traded_symbols)} symbols over {len(windows)} monthly windows. "
                "If Binance rejects monthly windows, the tool falls back to daily windows automatically."
            )

        for index, item in enumerate(traded_symbols, start=1):
            self._log(f"Importing spot trades for symbol {index}/{len(traded_symbols)} ({item.symbol})")
            symbol_records = self.get_spot_trades(item, start, end, windows=windows)
            self._log(f"Imported {len(symbol_records)} spot trade rows for {item.symbol}.")
            records.extend(symbol_records)
        return records

    def _load_cached_traded_symbols(self, symbol_by_name: dict[str, BinanceSymbol]) -> list[BinanceSymbol]:
        raw = get_sync_state(TRADED_SYMBOL_CACHE_KEY)
        if not raw:
            return []
        try:
            cached_names = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(cached_names, list):
            return []
        symbols = [symbol_by_name[name] for name in cached_names if isinstance(name, str) and name in symbol_by_name]
        return sorted(symbols, key=lambda item: item.symbol)

    def _save_cached_traded_symbols(self, symbols: list[BinanceSymbol]) -> None:
        names = sorted({item.symbol for item in symbols})
        set_sync_state(TRADED_SYMBOL_CACHE_KEY, json.dumps(names))
        self._log(f"Cached {len(names)} traded spot symbols for future incremental syncs.")

    def _detect_traded_symbols(self, symbols: list[BinanceSymbol]) -> list[BinanceSymbol]:
        traded_symbols: list[BinanceSymbol] = []
        started = time.monotonic()
        for index, item in enumerate(symbols, start=1):
            if index == 1 or index % 25 == 0 or index == len(symbols):
                elapsed = max(time.monotonic() - started, 0.1)
                per_symbol = elapsed / index
                remaining = int(per_symbol * (len(symbols) - index))
                self._log(
                    f"Detecting traded symbols: {index}/{len(symbols)} ({item.symbol}) | "
                    f"estimated remaining: {remaining}s"
                )
            if self._symbol_has_any_trades(item):
                traded_symbols.append(item)
                self._log(f"Detected account trade history for {item.symbol}.")
        self._log(f"Detected {len(traded_symbols)} symbols with account spot trades.")
        return traded_symbols

    def _symbol_has_any_trades(self, symbol: BinanceSymbol) -> bool:
        rows = self._signed_get(
            "/api/v3/myTrades",
            {"symbol": symbol.symbol, "limit": 1},
        )
        return isinstance(rows, list) and len(rows) > 0

    def get_spot_trades(
        self,
        symbol: BinanceSymbol,
        start: datetime,
        end: datetime,
        windows: list | None = None,
    ) -> list[NormalizedTransaction]:
        records: list[NormalizedTransaction] = []
        windows = windows or split_into_monthly_windows(start, end)
        started = time.monotonic()
        skipped_cached = 0
        for window_index, window in enumerate(windows, start=1):
            cache_key = self._empty_window_key("spot", symbol.symbol, window.start, window.end)
            if get_sync_state(cache_key):
                skipped_cached += 1
                continue
            if window_index == 1 or window_index % 10 == 0 or window_index == len(windows):
                elapsed = max(time.monotonic() - started, 0.1)
                per_window = elapsed / window_index
                remaining = int(per_window * (len(windows) - window_index))
                window_label = "daily" if self._is_daily_window(window.start, window.end) else "monthly"
                self._log(
                    f"{symbol.symbol}: {window_label} window {window_index}/{len(windows)} | "
                    f"estimated remaining for symbol: {remaining}s"
                )

            rows = self._request_spot_window(symbol, window.start, window.end)
            if rows is None:
                self._log(
                    f"{symbol.symbol}: Binance rejected a larger spot window. "
                    "Caching daily fallback for future syncs."
                )
                set_sync_state(SPOT_MONTHLY_UNSUPPORTED_KEY, "1")
                records.extend(self._get_spot_trades_daily(symbol, window.start, window.end))
                continue
            if not rows:
                set_sync_state(cache_key, "1")
                continue
            if len(rows) >= 1000 and not self._is_daily_window(window.start, window.end):
                self._log(
                    f"{symbol.symbol}: larger window returned 1000 rows. "
                    "Falling back to daily windows to avoid missing trades."
                )
                records.extend(self._get_spot_trades_daily(symbol, window.start, window.end))
                continue
            records.extend(self._normalize_spot_rows(symbol, rows))
            self._update_symbol_trade_range(symbol.symbol, rows)
            self._log(f"{symbol.symbol}: found {len(rows)} raw trade rows in current window.")
        if skipped_cached:
            self._log(f"{symbol.symbol}: skipped {skipped_cached} cached empty windows.")
        return records

    def _get_spot_trades_daily(self, symbol: BinanceSymbol, start: datetime, end: datetime) -> list[NormalizedTransaction]:
        records: list[NormalizedTransaction] = []
        daily_windows = split_into_daily_windows(start, end)
        skipped_cached = 0
        for day_index, day_window in enumerate(daily_windows, start=1):
            cache_key = self._empty_window_key("spot", symbol.symbol, day_window.start, day_window.end)
            if get_sync_state(cache_key):
                skipped_cached += 1
                continue
            if day_index == 1 or day_index % 30 == 0 or day_index == len(daily_windows):
                self._log(f"{symbol.symbol}: daily fallback window {day_index}/{len(daily_windows)}")
            rows = self._request_spot_window(symbol, day_window.start, day_window.end)
            if not rows:
                set_sync_state(cache_key, "1")
                continue
            records.extend(self._normalize_spot_rows(symbol, rows))
            self._update_symbol_trade_range(symbol.symbol, rows)
            self._log(f"{symbol.symbol}: found {len(rows)} raw trade rows in daily fallback window.")
        if skipped_cached:
            self._log(f"{symbol.symbol}: skipped {skipped_cached} cached empty daily fallback windows.")
        return records

    def _request_spot_window(self, symbol: BinanceSymbol, start: datetime, end: datetime) -> list[dict] | None:
        try:
            rows = self._signed_get(
                "/api/v3/myTrades",
                {
                    "symbol": symbol.symbol,
                    "startTime": _to_millis(start),
                    "endTime": _to_millis(end),
                    "limit": 1000,
                },
            )
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 400 and not self._is_daily_window(start, end):
                return None
            raise
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict)]

    def _normalize_spot_rows(self, symbol: BinanceSymbol, rows: list[dict]) -> list[NormalizedTransaction]:
        records: list[NormalizedTransaction] = []
        for row in rows:
            row["symbol"] = symbol.symbol
            records.append(normalize_spot_trade(row, symbol.base_asset, symbol.quote_asset))
        return records

    def _update_symbol_trade_range(self, symbol: str, rows: list[dict]) -> None:
        times = [int(row["time"]) for row in rows if row.get("time") is not None]
        if not times:
            return
        first_key = f"binance_spot_symbol_first_trade:{symbol}"
        last_key = f"binance_spot_symbol_last_trade:{symbol}"
        existing_first = get_sync_state(first_key)
        existing_last = get_sync_state(last_key)
        first_seen = min(times)
        last_seen = max(times)
        if not existing_first or first_seen < int(existing_first):
            set_sync_state(first_key, str(first_seen))
        if not existing_last or last_seen > int(existing_last):
            set_sync_state(last_key, str(last_seen))

    def _is_daily_window(self, start: datetime, end: datetime) -> bool:
        return (end - start) <= timedelta(days=1, seconds=1)

    def sync_convert_trades(self, start: datetime, end: datetime) -> list[NormalizedTransaction]:
        records: list[NormalizedTransaction] = []
        windows = split_into_daily_windows(start, end)
        skipped_cached = 0
        for window_index, window in enumerate(windows, start=1):
            cache_key = self._empty_window_key("convert", "tradeFlow", window.start, window.end)
            if get_sync_state(cache_key):
                skipped_cached += 1
                continue
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
            if not rows:
                set_sync_state(cache_key, "1")
                continue
            for row in rows:
                records.extend(normalize_convert_trade(row))
        if skipped_cached:
            self._log(f"Convert trades: skipped {skipped_cached} cached empty windows.")
        return records

    def sync_asset_rewards(self, start: datetime, end: datetime) -> list[NormalizedTransaction]:
        records: list[NormalizedTransaction] = []
        windows = split_into_daily_windows(start, end)
        skipped_cached = 0
        for window_index, window in enumerate(windows, start=1):
            cache_key = self._empty_window_key("asset_reward", "assetDividend", window.start, window.end)
            if get_sync_state(cache_key):
                skipped_cached += 1
                continue
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
            if not rows:
                set_sync_state(cache_key, "1")
                continue
            for row in rows:
                _append_if_valid(records, normalize_reward(row, product="asset_dividend", id_prefix="assetDividend"))
        if skipped_cached:
            self._log(f"Asset rewards: skipped {skipped_cached} cached empty windows.")
        return records

    def sync_simple_earn_rewards(self, start: datetime, end: datetime) -> list[NormalizedTransaction]:
        records: list[NormalizedTransaction] = []
        endpoints = [
            ("/sapi/v1/simple-earn/flexible/history/rewardsRecord", "simple_earn_flexible"),
            ("/sapi/v1/simple-earn/locked/history/rewardsRecord", "simple_earn_locked"),
        ]
        windows = split_into_daily_windows(start, end)
        for path, product in endpoints:
            endpoint_key = f"{UNAVAILABLE_ENDPOINT_PREFIX}:{product}"
            if get_sync_state(endpoint_key):
                self._log(f"Skipping unavailable Simple Earn endpoint cached earlier: {product}")
                continue
            self._log(f"Simple Earn endpoint: {product}")
            skipped_cached = 0
            for window_index, window in enumerate(windows, start=1):
                cache_key = self._empty_window_key("simple_earn", product, window.start, window.end)
                if get_sync_state(cache_key):
                    skipped_cached += 1
                    continue
                if window_index == 1 or window_index % 30 == 0 or window_index == len(windows):
                    self._log(f"{product} progress: window {window_index}/{len(windows)}")
                rows = self._fetch_numbered_optional(
                    path=path,
                    rows_key="rows",
                    page_size=100,
                    params={
                        "startTime": _to_millis(window.start),
                        "endTime": _to_millis(window.end),
                        "size": 100,
                    },
                    product=product,
                )
                if rows is None:
                    set_sync_state(endpoint_key, "1")
                    self._log(f"Simple Earn endpoint unavailable for this account/API key: {product}. Cached skip.")
                    break
                if not rows:
                    set_sync_state(cache_key, "1")
                    continue
                for row in rows:
                    _append_if_valid(records, normalize_reward(row, product=product, id_prefix=product))
            if skipped_cached:
                self._log(f"{product}: skipped {skipped_cached} cached empty windows.")
        return records

    def sync_transfers(self, start: datetime, end: datetime) -> list[NormalizedTransaction]:
        records: list[NormalizedTransaction] = []
        windows = split_into_daily_windows(start, end)
        skipped_cached = 0
        for window_index, window in enumerate(windows, start=1):
            if window_index == 1 or window_index % 30 == 0 or window_index == len(windows):
                self._log(f"Transfer progress: window {window_index}/{len(windows)}")

            deposit_key = self._empty_window_key("transfer", "deposit", window.start, window.end)
            if get_sync_state(deposit_key):
                skipped_cached += 1
            else:
                deposits = self._signed_get(
                    "/sapi/v1/capital/deposit/hisrec",
                    {"startTime": _to_millis(window.start), "endTime": _to_millis(window.end)},
                )
                deposit_rows = extract_rows(deposits)
                if not deposit_rows:
                    set_sync_state(deposit_key, "1")
                for row in deposit_rows:
                    _append_if_valid(records, normalize_transfer(row, "deposit", "deposit", True))

            withdrawal_key = self._empty_window_key("transfer", "withdrawal", window.start, window.end)
            if get_sync_state(withdrawal_key):
                skipped_cached += 1
            else:
                withdrawals = self._signed_get(
                    "/sapi/v1/capital/withdraw/history",
                    {"startTime": _to_millis(window.start), "endTime": _to_millis(window.end)},
                )
                withdrawal_rows = extract_rows(withdrawals)
                if not withdrawal_rows:
                    set_sync_state(withdrawal_key, "1")
                for row in withdrawal_rows:
                    _append_if_valid(records, normalize_transfer(row, "withdrawal", "withdrawal", False))
        if skipped_cached:
            self._log(f"Transfers: skipped {skipped_cached} cached empty windows.")
        return records

    def _fetch_numbered_optional(
        self,
        path: str,
        rows_key: str,
        page_size: int,
        params: dict[str, object],
        product: str,
    ) -> list[dict] | None:
        result: list[dict] = []
        page = 1
        while True:
            payload = dict(params)
            payload["current"] = page
            rows_payload = self._signed_get(path, payload, ignore_bad_request=True)
            if rows_payload is None:
                return None
            rows = extract_rows(rows_payload, rows_key)
            if not rows:
                break
            result.extend(rows)
            if len(rows) < page_size:
                break
            page += 1
        return result

    def _empty_window_key(self, product: str, item: str, start: datetime, end: datetime) -> str:
        return f"{EMPTY_WINDOW_PREFIX}:{product}:{item}:{_to_millis(start)}:{_to_millis(end)}"

    def _signed_get(
        self,
        path: str,
        params: dict[str, object] | None = None,
        ignore_bad_request: bool = False,
    ) -> dict | list | None:
        if not self.api_key or not self.api_secret:
            raise ValueError("Binance API key and secret are required for signed endpoints.")
        payload = dict(params or {})
        payload["timestamp"] = int(time.time() * 1000)
        query = urlencode(payload)
        signature = hmac.new(self.api_secret, query.encode("utf-8"), hashlib.sha256).hexdigest()
        url = f"{self.base_url}{path}?{query}&signature={signature}"
        response = with_retries(lambda: self.session.get(url, timeout=30))
        if ignore_bad_request and response.status_code == 400:
            self._log(f"Optional Binance endpoint returned 400 and will be skipped: {path}")
            return None
        response.raise_for_status()
        return response.json()
