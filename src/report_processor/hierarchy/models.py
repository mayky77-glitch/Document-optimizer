"""Small, privacy-safe contracts for hierarchical position filtering."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PositionCode:
    raw: str
    segments: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HierarchyEntry:
    row_id: str
    position_code: str | None
    amount: Decimal | None
    context: tuple[str, ...] = ()
    # A transactional row represents an independently measured work/material
    # line.  Some source books nest resource-detail lines below a work line;
    # such a work line must not be mistaken for a section total merely because
    # it has children.
    is_transactional: bool = False


@dataclass(frozen=True, slots=True)
class HierarchyIssue:
    code: str
    severity: str
    row_id: str | None = None
    related_row_ids: tuple[str, ...] = ()
    position_code: str | None = None
    parent_amount: Decimal | None = None
    direct_children_amount: Decimal | None = None
    delta: Decimal | None = None
    tolerance: Decimal | None = None


@dataclass(frozen=True, slots=True)
class HierarchyFilterResult:
    leaf_row_ids: tuple[str, ...]
    parent_row_ids: tuple[str, ...]
    issues: tuple[HierarchyIssue, ...]
    status: str
    warnings: tuple[str, ...]
    resource_detail_row_ids: tuple[str, ...] = ()
