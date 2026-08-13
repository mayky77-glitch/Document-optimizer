"""Immutable contracts for direct reconciliation reporting-period insertion."""

from __future__ import annotations

import hashlib
import json
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
    sheet_id: int
    worksheet_part: str
    quantity_column: int
    cost_column: int
    first_detail_row: int
    parent_span: tuple[int, int, int, int]
    historical_parent_label: str
    quantity_leaf_row: int
    cost_leaf_row: int
    quantity_leaf_label: str
    cost_leaf_label: str
    suffix_nonempty_count: int
    suffix_first_coordinate: str
    suffix_last_coordinate: str
    suffix_rightmost_coordinate: str
    suffix_coordinate_sha256: str

    @property
    def insertion_after_column(self) -> int:
        return self.cost_column


@dataclass(frozen=True, slots=True)
class ReconciliationPeriodInsertionPlan:
    contract_version: str
    source_sha256: str
    period: ReportingPeriod
    anchors: tuple[ReconciliationSheetAnchor, ...]
    worksheet_parts: tuple[tuple[str, str], ...]
    affected_parts: tuple[str, ...]
    selected_detail_rows: tuple[tuple[str, int], ...]
    idempotent: bool = False
    plan_digest: str = ""

    def __post_init__(self) -> None:
        if self.contract_version != "ReconciliationPeriodInsertion-1.0":
            raise ReconciliationPeriodError("PERIOD_INSERTION_PLAN_INVALID")
        canonical = self.canonical_bytes()
        digest = hashlib.sha256(canonical).hexdigest()
        if self.plan_digest and self.plan_digest != digest:
            raise ReconciliationPeriodError("PERIOD_INSERTION_PLAN_INVALID")
        object.__setattr__(self, "plan_digest", digest)

    def canonical_bytes(self) -> bytes:
        payload = {
            "anchors": [
                {
                    "boundary": item.insertion_after_column,
                    "cost_column": item.cost_column,
                    "cost_leaf_label": item.cost_leaf_label,
                    "cost_leaf_row": item.cost_leaf_row,
                    "first_detail_row": item.first_detail_row,
                    "parent_span": item.parent_span,
                    "historical_parent_label": item.historical_parent_label,
                    "quantity_column": item.quantity_column,
                    "quantity_leaf_label": item.quantity_leaf_label,
                    "quantity_leaf_row": item.quantity_leaf_row,
                    "sheet_id": item.sheet_id,
                    "sheet_name": item.sheet_name,
                    "suffix_nonempty_count": item.suffix_nonempty_count,
                    "suffix_first_coordinate": item.suffix_first_coordinate,
                    "suffix_last_coordinate": item.suffix_last_coordinate,
                    "suffix_rightmost_coordinate": item.suffix_rightmost_coordinate,
                    "suffix_coordinate_sha256": item.suffix_coordinate_sha256,
                    "worksheet_part": item.worksheet_part,
                }
                for item in sorted(self.anchors, key=lambda item: (item.sheet_name, item.sheet_id))
            ],
            "affected_parts": sorted(self.affected_parts),
            "contract_version": self.contract_version,
            "idempotent": self.idempotent,
            "period": self.period.value,
            "source_sha256": self.source_sha256,
            "selected_detail_rows": sorted(self.selected_detail_rows),
            "worksheet_parts": sorted(self.worksheet_parts),
        }
        return json.dumps(
            payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        ).encode()


@dataclass(frozen=True, slots=True)
class PreparedReconciliationTarget:
    path: str
    output_sha256: str
    plan: ReconciliationPeriodInsertionPlan
