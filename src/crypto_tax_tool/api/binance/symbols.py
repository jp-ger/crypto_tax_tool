from dataclasses import dataclass


@dataclass(frozen=True)
class BinanceSymbol:
    symbol: str
    base_asset: str
    quote_asset: str
    status: str


def parse_exchange_info(payload: dict) -> list[BinanceSymbol]:
    result: list[BinanceSymbol] = []
    for item in payload.get("symbols", []):
        result.append(
            BinanceSymbol(
                symbol=item["symbol"],
                base_asset=item["baseAsset"],
                quote_asset=item["quoteAsset"],
                status=item["status"],
            )
        )
    return result
