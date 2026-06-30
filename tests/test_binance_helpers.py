from datetime import UTC, datetime
from decimal import Decimal

from crypto_tax_tool.api.binance.normalizers import normalize_spot_trade
from crypto_tax_tool.api.binance.spot_sync import split_into_daily_windows
from crypto_tax_tool.api.binance.symbols import parse_exchange_info
from crypto_tax_tool.models.enums import TradeSide


def test_split_into_daily_windows() -> None:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    end = datetime(2025, 1, 3, 12, tzinfo=UTC)
    windows = split_into_daily_windows(start, end)
    assert len(windows) == 3
    assert windows[0].start == start
    assert windows[-1].end == end


def test_parse_exchange_info() -> None:
    payload = {"symbols": [{"symbol": "BTCUSDC", "baseAsset": "BTC", "quoteAsset": "USDC", "status": "TRADING"}]}
    symbols = parse_exchange_info(payload)
    assert symbols[0].symbol == "BTCUSDC"
    assert symbols[0].base_asset == "BTC"


def test_normalize_spot_trade_buy() -> None:
    row = {
        "symbol": "BTCUSDC",
        "id": 123,
        "orderId": 456,
        "price": "50000",
        "qty": "0.1",
        "quoteQty": "5000",
        "commission": "1",
        "commissionAsset": "USDC",
        "time": 1735689600000,
        "isBuyer": True,
    }
    tx = normalize_spot_trade(row, "BTC", "USDC")
    assert tx.side == TradeSide.BUY
    assert tx.asset == "BTC"
    assert tx.quantity == Decimal("0.1")
    assert tx.quote_asset == "USDC"
