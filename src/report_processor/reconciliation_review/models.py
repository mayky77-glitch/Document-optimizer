"""Typed, transport-neutral contracts for authoritative reconciliation review."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class ReviewAction(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"


class ReviewMode(StrEnum):
    QUANTITY_COST = "quantity_cost"
    COST_ONLY = "cost_only"


@dataclass(frozen=True, slots=True)
class ReviewRow:
    """The only source facts this domain needs to form a review group."""

    row_id: str
    display_name: str | None
    unit: str | None
    quantity: Decimal | None
    cost: Decimal | None
    proposed_category: str | None = None

    def __post_init__(self) -> None:
        if not self.row_id.strip():
            raise ValueError("row_id must not be empty")
        for value in (self.quantity, self.cost):
            if value is not None and (not isinstance(value, Decimal) or not value.is_finite()):
                raise ValueError("quantity and cost must be finite Decimals or None")


@dataclass(frozen=True, slots=True)
class ReviewGroup:
    """Membership-complete review group with an optimistic-concurrency version."""

    group_id: str
    version: str
    normalized_name: str | None
    normalized_unit: str | None
    member_ids: tuple[str, ...]
    proposed_category: str | None

    def __post_init__(self) -> None:
        if not self.member_ids or tuple(sorted(set(self.member_ids))) != self.member_ids:
            raise ValueError("member_ids must be non-empty, unique and sorted")


@dataclass(frozen=True, slots=True)
class ReviewDecision:
    """One controlled decision targeting either a group or a single source row."""

    action: ReviewAction
    mode: ReviewMode | None = None
    target_category: str | None = None
    group_id: str | None = None
    row_id: str | None = None
    version: str | None = None

    def __post_init__(self) -> None:
        if (self.group_id is None) == (self.row_id is None):
            raise ValueError("a decision must target exactly one group or row")
        if self.action is ReviewAction.ACCEPT:
            if self.mode is None or not _controlled_category(self.target_category):
                raise ValueError("an accepted decision needs a mode and target category")
        elif self.mode is not None or self.target_category is not None:
            raise ValueError("a rejected decision cannot carry category or mode")


@dataclass(frozen=True, slots=True)
class AppliedOverride:
    """Controlled inputs for matching and calculation after human review."""

    row_id: str
    target_category: str | None
    include_quantity: bool
    include_cost: bool
    action: ReviewAction | None


@dataclass(frozen=True, slots=True)
class FeedbackRecord:
    """Persistable resolution data; provenance intentionally stays outside this model."""

    name_key: str
    unit_key: str | None
    action: ReviewAction
    target_category: str | None = None
    mode: ReviewMode | None = None
    sequence: int = 0

    def __post_init__(self) -> None:
        if not self.name_key:
            raise ValueError("name_key must not be empty")
        if self.sequence < 0:
            raise ValueError("sequence must not be negative")
        if self.action is ReviewAction.ACCEPT:
            if self.mode is None or not _controlled_category(self.target_category):
                raise ValueError("accepted feedback needs category and mode")
        elif self.mode is not None or self.target_category is not None:
            raise ValueError("rejected feedback cannot carry category or mode")


def _controlled_category(value: str | None) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value.strip()) <= 200
