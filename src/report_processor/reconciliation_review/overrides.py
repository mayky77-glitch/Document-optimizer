"""Apply group and row review decisions without touching processing wiring."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from .models import AppliedOverride, ReviewAction, ReviewDecision, ReviewGroup, ReviewRow


def apply_overrides(
    rows: Iterable[ReviewRow], groups: Iterable[ReviewGroup], decisions: Iterable[ReviewDecision]
) -> dict[str, AppliedOverride]:
    """Return deterministic controlled inputs; a row decision wins over its group."""
    row_ids = {row.row_id for row in rows}
    group_values = tuple(groups)
    group_map = {group.group_id: group for group in group_values}
    if len(group_map) != len(group_values):
        raise ValueError("review groups must have unique group_id values")
    memberships = _memberships(group_map, row_ids)
    result: dict[str, AppliedOverride] = {}
    materialized = tuple(decisions)
    _reject_duplicate_targets(materialized)
    # Resolve group choices first regardless of request ordering. A targeted
    # row decision is the documented, deterministic exception to group fanout.
    for decision in materialized:
        if decision.group_id is None:
            continue
        targets = _targets(decision, group_map, row_ids)
        for row_id in targets:
            _apply(result, row_id, decision)
    for decision in materialized:
        if decision.row_id is None:
            continue
        _validate_row_version(decision, memberships)
        _apply(result, decision.row_id, decision)
    return result


def _targets(
    decision: ReviewDecision, groups: Mapping[str, ReviewGroup], row_ids: set[str]
) -> tuple[str, ...]:
    if decision.row_id is not None:
        if decision.row_id not in row_ids:
            raise ValueError("decision references an unknown row")
        return (decision.row_id,)
    group = groups.get(decision.group_id or "")
    if group is None:
        raise ValueError("decision references an unknown group")
    if decision.version is not None and decision.version != group.version:
        raise ValueError("decision version is stale")
    return group.member_ids


def _memberships(groups: Mapping[str, ReviewGroup], row_ids: set[str]) -> Mapping[str, ReviewGroup]:
    memberships: dict[str, ReviewGroup] = {}
    for group in groups.values():
        for row_id in group.member_ids:
            if row_id not in row_ids:
                raise ValueError("group references an unknown row")
            if row_id in memberships:
                raise ValueError("row belongs to multiple review groups")
            memberships[row_id] = group
    if set(memberships) != row_ids:
        raise ValueError("every row must belong to one review group")
    return memberships


def _validate_row_version(decision: ReviewDecision, memberships: Mapping[str, ReviewGroup]) -> None:
    assert decision.row_id is not None
    group = memberships.get(decision.row_id)
    if group is None:
        raise ValueError("decision references an unknown row")
    if decision.version is not None and decision.version != group.version:
        raise ValueError("decision version is stale")


def _reject_duplicate_targets(decisions: tuple[ReviewDecision, ...]) -> None:
    targets = [decision.group_id or decision.row_id for decision in decisions]
    if len(targets) != len(set(targets)):
        raise ValueError("multiple decisions target the same row or group")


def _apply(result: dict[str, AppliedOverride], row_id: str, decision: ReviewDecision) -> None:
    if decision.action is ReviewAction.REJECT:
        result.pop(row_id, None)
    else:
        result[row_id] = _application(row_id, decision)


def _application(row_id: str, decision: ReviewDecision) -> AppliedOverride:
    assert decision.mode is not None
    return AppliedOverride(
        row_id=row_id,
        target_category=decision.target_category,
        include_quantity=decision.mode.value == "quantity_cost",
        include_cost=True,
        action=ReviewAction.ACCEPT,
    )
