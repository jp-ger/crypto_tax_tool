from datetime import UTC, datetime
from decimal import Decimal

from crypto_tax_tool.models.balances import AssetBalance, BalanceSnapshot
from crypto_tax_tool.models.enums import TaxCategory, TradeSide, TransactionKind, TransactionSource
from crypto_tax_tool.models.transactions import NormalizedTransaction


def _dt_from_ms(value: int | str | None) -> datetime:
    if value is None or value == "":
        raise ValueError("Missing timestamp in Binance payload.")
    return datetime.fromtimestamp(int(value) / 1000, tz=UTC)


def _decimal(value: object, default: str = "0") -> Decimal:
    if value is None or value == "":
        return Decimal(default)
    return Decimal(str(value))


def normalize_spot_trade(payload: dict, base_asset: str, quote_asset: str) -> NormalizedTransaction:
    is_buyer = bool(payload.get("isBuyer"))
    qty = _decimal(payload["qty"])
    price = _decimal(payload["price"])
    quote_qty = _decimal(payload.get("quoteQty"), str(price * qty))
    fee_qty = _decimal(payload.get("commission"))
    dt = _dt_from_ms(payload["time"])

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


def normalize_convert_trade(payload: dict) -> list[NormalizedTransaction]:
    order_id = str(payload.get("orderId") or payload.get("quoteId") or payload)
    dt = _dt_from_ms(payload.get("createTime") or payload.get("orderTime"))
    from_asset = payload.get("fromAsset")
    to_asset = payload.get("toAsset")
    from_amount = _decimal(payload.get("fromAmount"))
    to_amount = _decimal(payload.get("toAmount"))

    return [
        NormalizedTransaction(
            source=TransactionSource.BINANCE,
            source_id=f"convert:sell:{order_id}",
            timestamp=dt,
            kind=TransactionKind.CONVERT,
            tax_category=TaxCategory.PRIVATE_DISPOSAL,
            asset=from_asset,
            quantity=from_amount,
            quote_asset=to_asset,
            quote_quantity=to_amount,
            side=TradeSide.SELL,
            product="convert",
            raw_type="convertTradeFlow",
            metadata=dict(payload),
        ),
        NormalizedTransaction(
            source=TransactionSource.BINANCE,
            source_id=f"convert:buy:{order_id}",
            timestamp=dt,
            kind=TransactionKind.CONVERT,
            tax_category=TaxCategory.PRIVATE_DISPOSAL,
            asset=to_asset,
            quantity=to_amount,
            quote_asset=from_asset,
            quote_quantity=from_amount,
            side=TradeSide.BUY,
            product="convert",
            raw_type="convertTradeFlow",
            metadata=dict(payload),
        ),
    ]


def normalize_reward(payload: dict, product: str, id_prefix: str) -> NormalizedTransaction | None:
    asset = payload.get("asset") or payload.get("rewardAsset")
    amount = payload.get("amount") or payload.get("rewards") or payload.get("rewardAmount")
    ts = payload.get("time") or payload.get("insertTime") or payload.get("completeTime")
    if not asset or amount is None or amount == "" or ts is None or ts == "":
        return None
    source_id = payload.get("id") or payload.get("tranId") or payload.get("uuid") or f"{asset}:{amount}:{ts}"
    return NormalizedTransaction(
        source=TransactionSource.BINANCE,
        source_id=f"{id_prefix}:{source_id}",
        timestamp=_dt_from_ms(ts),
        kind=TransactionKind.REWARD,
        tax_category=TaxCategory.OTHER_INCOME,
        asset=asset,
        quantity=_decimal(amount),
        product=product,
        raw_type=id_prefix,
        metadata=dict(payload),
    )


def normalize_transfer(payload: dict, product: str, id_prefix: str, is_deposit: bool) -> NormalizedTransaction | None:
    asset = payload.get("coin") or payload.get("asset")
    amount = payload.get("amount")
    ts = payload.get("insertTime") or payload.get("applyTime") or payload.get("successTime")
    if not asset or amount is None or amount == "" or ts is None or ts == "":
        return None
    source_id = payload.get("id") or payload.get("txId") or f"{asset}:{amount}:{ts}"
    return NormalizedTransaction(
        source=TransactionSource.BINANCE,
        source_id=f"{id_prefix}:{source_id}",
        timestamp=_dt_from_ms(ts),
        kind=TransactionKind.DEPOSIT if is_deposit else TransactionKind.WITHDRAWAL,
        tax_category=TaxCategory.NON_TAXABLE_TRANSFER,
        asset=asset,
        quantity=_decimal(amount),
        fee_asset=asset if not is_deposit else None,
        fee_quantity=_decimal(payload.get("transactionFee")) if not is_deposit else None,
        product=product,
        raw_type=id_prefix,
        metadata=dict(payload),
    )


def normalize_account_balances(payload: dict) -> BalanceSnapshot:
    balances: list[AssetBalance] = []
    for row in payload.get("balances", []):
        free = _decimal(row.get("free"))
        locked = _decimal(row.get("locked"))
        if free == 0 and locked == 0:
            continue
        balances.append(AssetBalance(asset=row["asset"], free=free, locked=locked))
    return BalanceSnapshot(source=TransactionSource.BINANCE, balances=balances)
