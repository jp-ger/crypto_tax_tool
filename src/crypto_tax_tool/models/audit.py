from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class AuditLotLink:
    lot_id: str
    source_transaction_id: str
    acquired_at: datetime
    quantity: Decimal
    cost_basis_eur: Decimal


@dataclass(frozen=True)
class AuditDisposalRecord:
    disposal_transaction_id: str
    asset: str
    quantity: Decimal
    proceeds_eur: Decimal
    cost_basis_eur: Decimal
    gain_eur: Decimal
    lot_links: list[AuditLotLink]
