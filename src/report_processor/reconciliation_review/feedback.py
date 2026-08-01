"""Feedback reuse and suppression for already resolved reconciliation groups."""

from __future__ import annotations

from collections.abc import Iterable

from .grouping import normalize_name, normalize_unit
from .models import FeedbackRecord, ReviewDecision, ReviewGroup


def latest_feedback(records: Iterable[FeedbackRecord]) -> dict[tuple[str, str | None], FeedbackRecord]:
    """Keep the highest-sequence record for each exact/group name and unit key."""
    result: dict[tuple[str, str | None], FeedbackRecord] = {}
    for record in records:
        key = normalize_name(record.name_key), normalize_unit(record.unit_key)
        if not key[0]:
            continue
        previous = result.get(key)
        if previous is None or record.sequence >= previous.sequence:
            result[key] = record
    return result


def feedback_for_group(
    group: ReviewGroup, records: Iterable[FeedbackRecord]
) -> FeedbackRecord | None:
    """Match exact normalized name or the accepted complete group prefix plus unit."""
    if not group.normalized_name:
        return None
    return latest_feedback(records).get((group.normalized_name, group.normalized_unit))


def suppress_resolved_groups(
    groups: Iterable[ReviewGroup], records: Iterable[FeedbackRecord]
) -> tuple[ReviewGroup, ...]:
    snapshot = latest_feedback(records)
    return tuple(
        group
        for group in groups
        if not group.normalized_name
        or (group.normalized_name, group.normalized_unit) not in snapshot
    )


def feedback_from_decision(group: ReviewGroup, decision: ReviewDecision, *, sequence: int) -> FeedbackRecord:
    """Convert a validated group decision to minimal reusable feedback."""
    if decision.group_id != group.group_id or not group.normalized_name:
        raise ValueError("feedback requires a named decision for this group")
    return FeedbackRecord(
        name_key=group.normalized_name,
        unit_key=group.normalized_unit,
        action=decision.action,
        target_category=decision.target_category,
        mode=decision.mode,
        sequence=sequence,
    )
