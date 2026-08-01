"""Apply group and row review decisions without touching processing wiring."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from .models import AppliedOverride, ReviewAction, ReviewDecision, ReviewGroup, ReviewRow


def apply_overrides(
    rows: Iterable[ReviewRow], groups: Iterable[ReviewGroup], decisions: Iterable[ReviewDecision]
) -> dict[str, AppliedOverride]:
    """Return deterministic controlled inputs; a row decision wins over its group."""
    row_ids = {row.row_id for row in rows}
    group_map = {group.group_id: group for group in groups}
    result: dict[str, AppliedOverride] = {}
    materialized = tuple(decisions)
    # Resolve group choices first regardless of request ordering. A targeted
    # row decision is the documented, deterministic exception to group fanout.
    for decision in materialized:
        if decision.group_id is None:
            continue
        targets = _targets(decision, group_map, row_ids)
        for row_id in targets:
            result[row_id] = _application(row_id, decision)
    for decision in materialized:
        if decision.row_id is None:
            continue
        result[decision.row_id] = _application(decision.row_id, decision)
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


def _application(row_id: str, decision: ReviewDecision) -> AppliedOverride:
    if decision.action is ReviewAction.REJECT:
        return AppliedOverride(row_id, None, False, False, ReviewAction.REJECT)
    assert decision.mode is not None
    return AppliedOverride(
        row_id=row_id,
        target_category=decision.target_category,
        include_quantity=decision.mode.value == "quantity_cost",
        include_cost=True,
        action=ReviewAction.ACCEPT,
    )
