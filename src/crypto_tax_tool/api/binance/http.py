import time
from collections.abc import Callable
from typing import TypeVar

import requests

T = TypeVar("T")


RETRY_STATUS_CODES = {418, 429, 500, 502, 503, 504}
OPTIONAL_BAD_REQUEST_PATHS = (
    "/api/v3/myTrades",
    "/sapi/v1/simple-earn/flexible/history/rewardsRecord",
    "/sapi/v1/simple-earn/locked/history/rewardsRecord",
)


class BinanceApiError(RuntimeError):
    pass


def _is_optional_bad_request(response: requests.Response) -> bool:
    if response.status_code != 400:
        return False
    return any(path in response.url for path in OPTIONAL_BAD_REQUEST_PATHS)


def with_retries(call: Callable[[], requests.Response], attempts: int = 5) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = call()
            if _is_optional_bad_request(response):
                return response
            if response.status_code not in RETRY_STATUS_CODES:
                response.raise_for_status()
                return response
            retry_after = response.headers.get("Retry-After")
            wait_seconds = float(retry_after) if retry_after else min(2**attempt, 30)
            time.sleep(wait_seconds)
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(min(2**attempt, 30))
    if last_error:
        raise BinanceApiError(str(last_error)) from last_error
    raise BinanceApiError("Binance API request failed after retries.")
