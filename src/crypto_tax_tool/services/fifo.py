from collections import defaultdict, deque
from decimal import Decimal

from crypto_tax_tool.models.enums import TaxCategory, TradeSide, TransactionKind
from crypto_tax_tool.models.lots import AssetLot, DisposalMatch
from crypto_tax_tool.models.transactions import NormalizedTransaction
from crypto_tax_tool.services.pricing import HistoricalPriceService


class InsufficientLotsError(RuntimeError):
    pass


class FifoEngine:
    def __init__(self, price_service: HistoricalPriceService) -> None:
        self.price_service = price_service

    def process(self, transactions: list[NormalizedTransaction]) -> list[DisposalMatch]:
        lots: dict[str, deque[AssetLot]] = defaultdict(deque)
        matches: list[DisposalMatch] = []
        for tx in sorted(transactions, key=lambda item: item.timestamp):
            if self._is_buy_or_income(tx):
                lots[tx.asset].append(self._create_lot(tx))
            elif self._is_sell(tx):
                asset = tx.quote_asset or tx.asset
                matches.extend(self._match_sale(lots[asset], tx, asset))
        return matches

    def _is_buy_or_income(self, tx: NormalizedTransaction) -> bool:
        if tx.kind in {TransactionKind.REWARD, TransactionKind.INCOME}:
            return tx.tax_category != TaxCategory.NON_TAXABLE_TRANSFER
        return tx.kind in {TransactionKind.TRADE, TransactionKind.CONVERT} and tx.side == TradeSide.BUY

    def _is_sell(self, tx: NormalizedTransaction) -> bool:
        return tx.kind in {TransactionKind.TRADE, TransactionKind.CONVERT} and tx.side == TradeSide.SELL

    def _create_lot(self, tx: NormalizedTransaction) -> AssetLot:
        if tx.quote_asset == "EUR" and tx.quote_quantity is not None:
            cost_basis = tx.quote_quantity
        else:
            price = self.price_service.get_price(tx.asset, "EUR", tx.timestamp)
            cost_basis = tx.quantity * price.price
        return AssetLot(
            asset=tx.asset,
            acquired_at=tx.timestamp,
            quantity=tx.quantity,
            remaining_quantity=tx.quantity,
            cost_basis_eur=cost_basis,
            source_transaction_id=tx.source_id,
        )

    def _match_sale(
        self, lots: deque[AssetLot], tx: NormalizedTransaction, asset: str
    ) -> list[DisposalMatch]:
        amount_needed = tx.quote_quantity or tx.quantity
        price = self.price_service.get_price(asset, "EUR", tx.timestamp)
        proceeds_total = amount_needed * price.price
        amount_left = amount_needed
        matches: list[DisposalMatch] = []
        while amount_left > 0:
            if not lots:
                raise InsufficientLotsError(f"No FIFO lot available for {asset} sale.")
            lot = lots[0]
            used = min(lot.remaining_quantity, amount_left)
            cost_basis = lot.cost_basis_eur * (used / lot.quantity)
            proceeds = proceeds_total * (used / amount_needed)
            matches.append(
                DisposalMatch(
                    disposal_transaction_id=tx.source_id,
                    lot_id=lot.id,
                    asset=asset,
                    quantity=used,
                    acquired_at=lot.acquired_at,
                    disposed_at=tx.timestamp,
                    cost_basis_eur=cost_basis,
                    proceeds_eur=proceeds,
                )
            )
            lot.remaining_quantity -= used
            amount_left -= used
            if lot.remaining_quantity <= 0:
                lots.popleft()
        return matches
