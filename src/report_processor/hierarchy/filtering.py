"""Select measured work rows without counting section totals or their resources twice."""

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
    """Keep the transactional frontier and return privacy-safe integrity signals.

    A structural parent without its own line metrics is a section aggregate and
    is excluded.  A structural parent with line metrics is a measured work row;
    it is retained while its nested resource-detail rows are excluded.  When
    callers do not provide ``is_transactional`` the legacy leaf-only behaviour
    remains intact.
    """
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
    duplicate_keys = {key for key, duplicates in by_context_code.items() if len(duplicates) > 1}
    row_keys = {entry.row_id: (entry.context, code.segments) for entry, code in parsed}

    children_by_parent: dict[tuple[tuple[str, ...], tuple[str, ...]], list[HierarchyEntry]] = (
        defaultdict(list)
    )
    descendants_by_parent: dict[tuple[tuple[str, ...], tuple[str, ...]], list[HierarchyEntry]] = (
        defaultdict(list)
    )
    transactional_descendants_by_parent: dict[
        tuple[tuple[str, ...], tuple[str, ...]], list[HierarchyEntry]
    ] = defaultdict(list)
    for entry, code in parsed:
        parent = _parent_key(code)
        if parent is not None:
            children_by_parent[(entry.context, parent)].append(entry)
        for depth in range(1, len(code.segments)):
            ancestor = (entry.context, code.segments[:depth])
            descendants_by_parent[ancestor].append(entry)
            if entry.is_transactional:
                transactional_descendants_by_parent[ancestor].append(entry)
    parents: set[str] = set()
    resource_details: set[str] = set()
    for entry, code in parsed:
        direct_children = children_by_parent.get((entry.context, code.segments), [])
        if not direct_children:
            continue
        # A duplicated position has no unambiguous structural identity. Keep
        # every affected row visible to downstream matching and audit.
        if (entry.context, code.segments) in duplicate_keys:
            continue
        if entry.is_transactional:
            resource_details.update(
                child.row_id
                for child in descendants_by_parent[(entry.context, code.segments)]
                if row_keys.get(child.row_id) not in duplicate_keys
            )
            continue
        parents.add(entry.row_id)
        compared_rows = (
            transactional_descendants_by_parent.get((entry.context, code.segments))
            or direct_children
        )
        amounts = [child.amount for child in compared_rows]
        if entry.amount is None or any(amount is None for amount in amounts):
            issues.append(
                HierarchyIssue(
                    "HIERARCHY_MISSING_DIRECT_CHILD_COST",
                    "warning",
                    entry.row_id,
                    tuple(child.row_id for child in compared_rows),
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
                        tuple(child.row_id for child in compared_rows),
                        code.raw,
                        entry.amount,
                        children_amount,
                        delta,
                        _TOLERANCE,
                    )
                )
    excluded = parents | resource_details
    leaves = tuple(entry.row_id for entry in entries if entry.row_id not in excluded)
    parent_rows = tuple(entry.row_id for entry in entries if entry.row_id in parents)
    resource_detail_rows = tuple(
        entry.row_id for entry in entries if entry.row_id in resource_details
    )
    warnings = tuple(dict.fromkeys(issue.code for issue in issues))
    return HierarchyFilterResult(
        leaves,
        parent_rows,
        tuple(issues),
        "WARNING" if issues else "OK",
        warnings,
        resource_detail_rows,
    )
