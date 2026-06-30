from datetime import UTC, datetime
from decimal import Decimal

from crypto_tax_tool.models.enums import TaxCategory, TradeSide, TransactionKind, TransactionSource
from crypto_tax_tool.models.transactions import NormalizedTransaction


def normalize_spot_trade(payload: dict, base_asset: str, quote_asset: str) -> NormalizedTransaction:
    is_buyer = bool(payload.get("isBuyer"))
    qty = Decimal(str(payload["qty"]))
    price = Decimal(str(payload["price"]))
    quote_qty = Decimal(str(payload.get("quoteQty", price * qty)))
    fee_qty = Decimal(str(payload.get("commission", "0")))
    dt = datetime.fromtimestamp(int(payload["time"]) / 1000, tz=UTC)

    return NormalizedTransaction(
        source=TransactionSource.BINANCE,
        source_id=f"spot:{payload['symbol']}:{payload['id']}",
        timestamp=dt,
        kind=TransactionKind.TRADE,
        tax_category=TaxCategory.PRIVATE_DISPOSAL,
        asset=base_asset if is_buyer else quote_asset,
        quantity=qty if is_buyer else quote_qty,
        quote_asset=quote_asset if is_buyer else base_asset,
        quote_quantity=quote_qty if is_buyer else qty,
        fee_asset=payload.get("commissionAsset"),
        fee_quantity=fee_qty,
        side=TradeSide.BUY if is_buyer else TradeSide.SELL,
        product="spot",
        raw_type="myTrades",
        metadata={"symbol": payload["symbol"], "orderId": payload.get("orderId")},
    )
