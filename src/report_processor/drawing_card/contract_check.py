"""Pure contract-cost discrepancy checks for drawing-card rows."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .models import DrawingCardResultRow

CONTRACT_COST_TOLERANCE_RUB = Decimal(1000)
CONTRACT_COST_EXCEEDED = "performed_cost_exceeds_contract"
CONTRACT_QUANTITY_WITHOUT_COST = "contract_quantity_without_cost"


@dataclass(frozen=True, slots=True)
class ContractCostViolation:
    """A contract-cost inconsistency that must be visible in the report log."""

    row: DrawingCardResultRow
    issue_code: str
    difference_rub: Decimal | None = None


def find_contract_cost_violations(
    rows: list[DrawingCardResultRow],
) -> list[ContractCostViolation]:
    """Return missing contract costs and performed-cost overages."""

    violations: list[ContractCostViolation] = []
    for row in rows:
        if row.contract_quantity != 0 and row.contract_total_cost == 0:
            violations.append(
                ContractCostViolation(
                    row=row,
                    issue_code=CONTRACT_QUANTITY_WITHOUT_COST,
                )
            )
            continue
        difference = row.performed_total_cost - row.contract_total_cost
        if difference > CONTRACT_COST_TOLERANCE_RUB:
            violations.append(
                ContractCostViolation(
                    row=row,
                    issue_code=CONTRACT_COST_EXCEEDED,
                    difference_rub=difference,
                )
            )
    return violations
