from decimal import Decimal

from crypto_tax_tool.models.transactions import NormalizedTransaction
from crypto_tax_tool.services.pricing import HistoricalPriceService


class FeeService:
    def __init__(self, price_service: HistoricalPriceService) -> None:
        self.price_service = price_service

    def fee_value_eur(self, tx: NormalizedTransaction) -> Decimal:
        if not tx.fee_asset or not tx.fee_quantity:
            return Decimal("0")
        if tx.fee_asset == "EUR":
            return tx.fee_quantity
        price = self.price_service.get_price(tx.fee_asset, "EUR", tx.timestamp)
        return tx.fee_quantity * price.price
