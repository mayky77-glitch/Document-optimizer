"""Pure contract-cost discrepancy checks for drawing-card rows."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .models import DrawingCardResultRow

CONTRACT_COST_TOLERANCE_RUB = Decimal(1000)


@dataclass(frozen=True, slots=True)
class ContractCostViolation:
    """A performed cost that exceeds its contract cost beyond the tolerance."""

    row: DrawingCardResultRow
    difference_rub: Decimal


def find_contract_cost_violations(
    rows: list[DrawingCardResultRow],
) -> list[ContractCostViolation]:
    """Return only costs exceeding the contract by more than exactly 1,000 RUB."""

    return [
        ContractCostViolation(row=row, difference_rub=difference)
        for row in rows
        if (difference := row.performed_total_cost - row.contract_total_cost)
        > CONTRACT_COST_TOLERANCE_RUB
    ]
