from datetime import datetime
from decimal import Decimal

from crypto_tax_tool.database.sqlite_store import get_cached_price, save_price
from crypto_tax_tool.models.prices import HistoricalPrice


class PriceNotFoundError(LookupError):
    pass


class PriceProvider:
    provider_name = "base"

    def get_price(self, asset: str, quote_asset: str, timestamp: datetime) -> HistoricalPrice | None:
        raise NotImplementedError


class StaticPriceProvider(PriceProvider):
    provider_name = "static"

    def __init__(self, prices: dict[tuple[str, str], Decimal]) -> None:
        self.prices = prices

    def get_price(self, asset: str, quote_asset: str, timestamp: datetime) -> HistoricalPrice | None:
        value = self.prices.get((asset, quote_asset))
        if value is None:
            return None
        return HistoricalPrice(
            asset=asset,
            quote_asset=quote_asset,
            timestamp=timestamp,
            price=value,
            provider=self.provider_name,
            pair=f"{asset}{quote_asset}",
        )


class HistoricalPriceService:
    def __init__(self, providers: list[PriceProvider] | None = None) -> None:
        self.providers = providers or []

    def get_price(self, asset: str, quote_asset: str, timestamp: datetime) -> HistoricalPrice:
        cached = get_cached_price(asset, quote_asset, timestamp)
        if cached:
            return cached

        for provider in self.providers:
            price = provider.get_price(asset, quote_asset, timestamp)
            if price:
                save_price(price)
                return price

        raise PriceNotFoundError(f"No price found for {asset}/{quote_asset} at {timestamp.isoformat()}.")
