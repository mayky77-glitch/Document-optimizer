"""Filter aggregate rows and reconcile each aggregate with direct children."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from itertools import pairwise

from .models import HierarchyEntry, HierarchyFilterResult, HierarchyIssue, PositionCode
from .positions import parse_position_code

_TOLERANCE = Decimal("0.01")


def _parent_key(code: PositionCode) -> tuple[str, ...] | None:
    return code.segments[:-1] or None


def _gap_issues(entries: list[tuple[HierarchyEntry, PositionCode]]) -> list[HierarchyIssue]:
    groups: dict[
        tuple[tuple[str, ...], tuple[str, ...]], list[tuple[HierarchyEntry, PositionCode]]
    ] = defaultdict(list)
    for entry, code in entries:
        parent = _parent_key(code)
        if parent is not None:
            groups[(entry.context, parent)].append((entry, code))
    issues: list[HierarchyIssue] = []
    for siblings in groups.values():
        numbers = sorted(
            {int(code.segments[-1]) for _, code in siblings if code.segments[-1].isdigit()}
        )
        if len(numbers) > 1 and any(right - left > 1 for left, right in pairwise(numbers)):
            issues.append(HierarchyIssue("HIERARCHY_POSITION_GAP", "warning"))
    return issues


def filter_aggregate_rows(
    entries: list[HierarchyEntry] | tuple[HierarchyEntry, ...],
) -> HierarchyFilterResult:
    """Keep leaves in input order and return only non-sensitive integrity signals."""
    parsed: list[tuple[HierarchyEntry, PositionCode]] = []
    issues: list[HierarchyIssue] = []
    by_context_code: dict[tuple[tuple[str, ...], tuple[str, ...]], list[HierarchyEntry]] = (
        defaultdict(list)
    )
    for entry in entries:
        code = parse_position_code(entry.position_code)
        if code is None:
            continue
        parsed.append((entry, code))
        by_context_code[(entry.context, code.segments)].append(entry)
    for duplicates in by_context_code.values():
        if len(duplicates) > 1:
            issues.append(
                HierarchyIssue(
                    "HIERARCHY_DUPLICATE_POSITION",
                    "warning",
                    related_row_ids=tuple(item.row_id for item in duplicates),
                )
            )
    issues.extend(_gap_issues(parsed))

    children_by_parent: dict[tuple[tuple[str, ...], tuple[str, ...]], list[HierarchyEntry]] = (
        defaultdict(list)
    )
    for entry, code in parsed:
        parent = _parent_key(code)
        if parent is not None:
            children_by_parent[(entry.context, parent)].append(entry)
    parents: set[str] = set()
    for entry, code in parsed:
        direct_children = children_by_parent.get((entry.context, code.segments), [])
        if not direct_children:
            continue
        parents.add(entry.row_id)
        amounts = [child.amount for child in direct_children]
        if entry.amount is None or any(amount is None for amount in amounts):
            issues.append(
                HierarchyIssue(
                    "HIERARCHY_MISSING_DIRECT_CHILD_COST",
                    "warning",
                    entry.row_id,
                    tuple(child.row_id for child in direct_children),
                    code.raw,
                    entry.amount,
                    tolerance=_TOLERANCE,
                )
            )
        else:
            children_amount = sum(amounts, Decimal("0"))
            delta = entry.amount - children_amount
            if abs(delta) > _TOLERANCE:
                issues.append(
                    HierarchyIssue(
                        "HIERARCHY_COST_MISMATCH",
                        "warning",
                        entry.row_id,
                        tuple(child.row_id for child in direct_children),
                        code.raw,
                        entry.amount,
                        children_amount,
                        delta,
                        _TOLERANCE,
                    )
                )
    leaves = tuple(entry.row_id for entry in entries if entry.row_id not in parents)
    parent_rows = tuple(entry.row_id for entry in entries if entry.row_id in parents)
    warnings = tuple(dict.fromkeys(issue.code for issue in issues))
    return HierarchyFilterResult(
        leaves, parent_rows, tuple(issues), "WARNING" if issues else "OK", warnings
    )
