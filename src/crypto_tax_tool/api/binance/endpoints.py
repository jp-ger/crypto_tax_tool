from dataclasses import dataclass


@dataclass(frozen=True)
class BinanceEndpoint:
    name: str
    path: str
    signed: bool = True
    notes: str = ""


SPOT_ACCOUNT = BinanceEndpoint("spot_account", "/api/v3/account")
SPOT_TRADES = BinanceEndpoint("spot_trades", "/api/v3/myTrades")
EXCHANGE_INFO = BinanceEndpoint("exchange_info", "/api/v3/exchangeInfo", signed=False)
CONVERT_TRADES = BinanceEndpoint("convert_trades", "/sapi/v1/convert/tradeFlow")
ASSET_DIVIDENDS = BinanceEndpoint("asset_dividends", "/sapi/v1/asset/assetDividend")
DEPOSIT_HISTORY = BinanceEndpoint("deposit_history", "/sapi/v1/capital/deposit/hisrec")
WITHDRAWAL_HISTORY = BinanceEndpoint("withdrawal_history", "/sapi/v1/capital/withdraw/history")
FLEXIBLE_REWARDS = BinanceEndpoint("flexible_rewards", "/sapi/v1/simple-earn/flexible/history/rewardsRecord")
LOCKED_REWARDS = BinanceEndpoint("locked_rewards", "/sapi/v1/simple-earn/locked/history/rewardsRecord")
STAKING_REWARDS = BinanceEndpoint("staking_rewards", "/sapi/v1/staking/stakingRecord")

ALL_ENDPOINTS = [
    SPOT_ACCOUNT,
    SPOT_TRADES,
    EXCHANGE_INFO,
    CONVERT_TRADES,
    ASSET_DIVIDENDS,
    DEPOSIT_HISTORY,
    WITHDRAWAL_HISTORY,
    FLEXIBLE_REWARDS,
    LOCKED_REWARDS,
    STAKING_REWARDS,
]
