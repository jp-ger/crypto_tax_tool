import hashlib
import hmac
import time
from datetime import datetime
from urllib.parse import urlencode

import requests

from crypto_tax_tool.api.exchange_base import ExchangeClient
from crypto_tax_tool.models.transactions import NormalizedTransaction
from crypto_tax_tool.settings import get_settings


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

    def sync_transactions(self, start: datetime, end: datetime) -> list[NormalizedTransaction]:
        # Placeholder: next sprint will add product-specific loaders.
        return []

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
