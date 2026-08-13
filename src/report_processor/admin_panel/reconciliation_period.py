"""Immutable contracts for direct reconciliation reporting-period insertion."""

from __future__ import annotations

import re
from dataclasses import dataclass

_PERIOD = re.compile(r"(?:19|20)\d{2}-(?:0[1-9]|1[0-2])\Z")
_MONTHS = (
    "январь",
    "февраль",
    "март",
    "апрель",
    "май",
    "июнь",
    "июль",
    "август",
    "сентябрь",
    "октябрь",
    "ноябрь",
    "декабрь",
)


class ReconciliationPeriodError(ValueError):
    """A period insertion cannot safely be planned or published."""


@dataclass(frozen=True, slots=True)
class ReportingPeriod:
    """Canonical user-selected reporting month (``YYYY-MM`` only)."""

    value: str

    def __post_init__(self) -> None:
        if not _PERIOD.fullmatch(self.value):
            raise ReconciliationPeriodError("REPORTING_PERIOD_INVALID")

    @classmethod
    def parse(cls, value: str) -> ReportingPeriod:
        if not isinstance(value, str):
            raise ReconciliationPeriodError("REPORTING_PERIOD_INVALID")
        return cls(value)

    @property
    def year(self) -> int:
        return int(self.value[:4])

    @property
    def month(self) -> int:
        return int(self.value[5:])

    @property
    def label(self) -> str:
        return f"{_MONTHS[self.month - 1].capitalize()} {self.year}"


@dataclass(frozen=True, slots=True)
class ReconciliationSheetAnchor:
    sheet_name: str
    quantity_column: int
    cost_column: int
    first_detail_row: int

    @property
    def insertion_after_column(self) -> int:
        return self.cost_column


@dataclass(frozen=True, slots=True)
class ReconciliationPeriodInsertionPlan:
    source_sha256: str
    period: ReportingPeriod
    anchors: tuple[ReconciliationSheetAnchor, ...]
    worksheet_parts: tuple[tuple[str, str], ...]
    idempotent: bool = False


@dataclass(frozen=True, slots=True)
class PreparedReconciliationTarget:
    path: str
    output_sha256: str
    plan: ReconciliationPeriodInsertionPlan
