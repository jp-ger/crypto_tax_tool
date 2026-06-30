from datetime import UTC, datetime
from decimal import Decimal

from crypto_tax_tool.models.fifo_state import AssetLot
from crypto_tax_tool.services.fifo_engine import FifoEngine


def test_fifo_uses_oldest_lots_first() -> None:
    engine = FifoEngine()
    engine.add_lot(
        AssetLot(
            asset="BTC",
            acquired_at=datetime(2021, 1, 1, tzinfo=UTC),
            quantity=Decimal("0.4"),
            remaining_quantity=Decimal("0.4"),
            cost_basis_eur=Decimal("8000"),
            source_transaction_id="buy1",
        )
    )
    engine.add_lot(
        AssetLot(
            asset="BTC",
            acquired_at=datetime(2023, 1, 1, tzinfo=UTC),
            quantity=Decimal("0.3"),
            remaining_quantity=Decimal("0.3"),
            cost_basis_eur=Decimal("9000"),
            source_transaction_id="buy2",
        )
    )

    usages = engine.use(
        asset="BTC",
        quantity=Decimal("0.5"),
        value_eur=Decimal("25000"),
        used_at=datetime(2025, 1, 1, tzinfo=UTC),
    )

    assert len(usages) == 2
    assert usages[0].quantity == Decimal("0.4")
    assert usages[0].cost_basis_eur == Decimal("8000")
    assert usages[1].quantity == Decimal("0.1")
    assert usages[1].cost_basis_eur == Decimal("3000")
    assert len(tuple(engine.open_lots("BTC"))) == 1
