from enum import StrEnum


class TransactionSource(StrEnum):
    BINANCE = "binance"
    MANUAL = "manual"


class TransactionKind(StrEnum):
    TRADE = "trade"
    CONVERT = "convert"
    REWARD = "reward"
    INCOME = "income"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    FEE = "fee"
    ADJUSTMENT = "adjustment"


class TradeSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class TaxCategory(StrEnum):
    PRIVATE_DISPOSAL = "private_disposal"
    OTHER_INCOME = "other_income"
    NON_TAXABLE_TRANSFER = "non_taxable_transfer"
    UNKNOWN = "unknown"
