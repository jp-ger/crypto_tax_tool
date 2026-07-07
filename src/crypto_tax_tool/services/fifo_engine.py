from collections import defaultdict, deque
from collections.abc import Iterable
from decimal import Decimal

from crypto_tax_tool.models.fifo_state import AssetLot, LotUsage


class InsufficientInventoryError(RuntimeError):
    def __init__(
        self,
        asset: str,
        missing_quantity: Decimal,
        requested_quantity: Decimal,
        matches: list[LotUsage] | None = None,
    ) -> None:
        self.asset = asset
        self.missing_quantity = missing_quantity
        self.requested_quantity = requested_quantity
        self.matches = matches or []
        super().__init__(f"Not enough inventory for {asset}: missing {missing_quantity}.")


class FifoEngine:
    def __init__(self) -> None:
        self._lots: dict[str, deque[AssetLot]] = defaultdict(deque)

    def add_lot(self, lot: AssetLot) -> None:
        if lot.remaining_quantity <= 0:
            return
        self._lots[lot.asset].append(lot)

    def use(self, asset: str, quantity: Decimal, value_eur: Decimal, used_at) -> list[LotUsage]:
        if quantity <= 0:
            return []
        lots = self._lots[asset]
        remaining = quantity
        result: list[LotUsage] = []

        while remaining > 0:
            if not lots:
                raise InsufficientInventoryError(
                    asset=asset,
                    missing_quantity=remaining,
                    requested_quantity=quantity,
                    matches=result,
                )
            lot = lots[0]
            used_quantity = min(lot.remaining_quantity, remaining)
            cost_share = lot.cost_basis_eur * used_quantity / lot.remaining_quantity
            value_share = value_eur * used_quantity / quantity
            result.append(
                LotUsage(
                    lot_id=lot.id,
                    asset=asset,
                    acquired_at=lot.acquired_at,
                    used_at=used_at,
                    quantity=used_quantity,
                    cost_basis_eur=cost_share,
                    value_eur=value_share,
                    source_transaction_id=lot.source_transaction_id,
                )
            )
            lot.remaining_quantity -= used_quantity
            lot.cost_basis_eur -= cost_share
            remaining -= used_quantity
            if lot.remaining_quantity == 0:
                lots.popleft()
        return result

    def open_lots(self, asset: str | None = None) -> Iterable[AssetLot]:
        if asset is not None:
            return tuple(self._lots[asset])
        all_lots: list[AssetLot] = []
        for lots in self._lots.values():
            all_lots.extend(lots)
        return tuple(all_lots)
