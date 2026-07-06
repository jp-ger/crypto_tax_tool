from datetime import UTC, datetime
from decimal import Decimal

from crypto_tax_tool.api.binance.normalizers import normalize_convert_trade, normalize_spot_trade, normalize_transfer
from crypto_tax_tool.models.enums import TradeSide, TransactionKind


def test_normalize_spot_buy() -> None:
    tx = normalize_spot_trade(
        {
            "symbol": "BTCUSDC",
            "id": 1,
            "orderId": 10,
            "price": "50000",
            "qty": "0.1",
            "quoteQty": "5000",
            "commission": "1",
            "commissionAsset": "USDC",
            "time": 1710000000000,
            "isBuyer": True,
        },
        base_asset="BTC",
        quote_asset="USDC",
    )

    assert tx.kind == TransactionKind.TRADE
    assert tx.side == TradeSide.BUY
    assert tx.asset == "BTC"
    assert tx.quantity == Decimal("0.1")
    assert tx.quote_asset == "USDC"
    assert tx.quote_quantity == Decimal("5000")


def test_normalize_convert_creates_two_legs() -> None:
    legs = normalize_convert_trade(
        {
            "orderId": "abc",
            "fromAsset": "BTC",
            "toAsset": "ETH",
            "fromAmount": "0.1",
            "toAmount": "2",
            "createTime": 1710000000000,
        }
    )

    assert len(legs) == 2
    assert legs[0].side == TradeSide.SELL
    assert legs[0].asset == "BTC"
    assert legs[1].side == TradeSide.BUY
    assert legs[1].asset == "ETH"


def test_normalize_transfer_accepts_datetime_string() -> None:
    tx = normalize_transfer(
        {
            "coin": "USDC",
            "amount": "10",
            "applyTime": "2024-04-26 06:42:24",
            "txId": "abc",
            "transactionFee": "0.1",
        },
        product="withdrawal",
        id_prefix="withdrawal",
        is_deposit=False,
    )

    assert tx is not None
    assert tx.timestamp == datetime(2024, 4, 26, 6, 42, 24, tzinfo=UTC)
    assert tx.fee_quantity == Decimal("0.1")
