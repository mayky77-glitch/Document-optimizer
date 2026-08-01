"""Safe payload shaping for authoritative reconciliation-review screens."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import ROUND_HALF_UP, Decimal

from report_processor.reconciliation_review import ReviewDecision, ReviewGroup, ReviewRow


def reconciliation_review_group_payload(
    group: ReviewGroup,
    rows: Mapping[str, ReviewRow],
    decisions: Iterable[ReviewDecision] = (),
) -> dict[str, object]:
    """Return only controlled identifiers and human review values.

    This deliberately does not accept arbitrary source mappings, so paths,
    provenance, warnings and upstream metrics cannot leak through the payload.
    """
    member_rows = tuple(rows[row_id] for row_id in group.member_ids)
    selected = _selected_decision(group, decisions)
    return {
        "group_id": group.group_id,
        "version": group.version,
        "proposed_category_id": group.proposed_category,
        "selected_category_id": selected.target_category if selected else None,
        "action": selected.action.value if selected else None,
        "mode": selected.mode.value if selected and selected.mode else None,
        "members": [_member_payload(row) for row in member_rows],
    }


def reconciliation_review_payload(
    groups: Iterable[ReviewGroup],
    rows: Mapping[str, ReviewRow],
    decisions: Iterable[ReviewDecision] = (),
) -> list[dict[str, object]]:
    """Serialize global groups in stable identity order."""
    decision_snapshot = tuple(decisions)
    return [
        reconciliation_review_group_payload(group, rows, decision_snapshot)
        for group in sorted(groups, key=lambda item: item.group_id)
    ]


def _selected_decision(
    group: ReviewGroup, decisions: Iterable[ReviewDecision]
) -> ReviewDecision | None:
    group_choice = next((item for item in decisions if item.group_id == group.group_id), None)
    row_choices = [item for item in decisions if item.row_id in group.member_ids]
    # A group card has one selected decision only when all its members agree.
    if row_choices:
        first = row_choices[0]
        if len(row_choices) == len(group.member_ids) and all(
            _same_choice(item, first) for item in row_choices
        ):
            return first
        return None
    return group_choice


def _same_choice(left: ReviewDecision, right: ReviewDecision) -> bool:
    return (
        left.action is right.action
        and left.mode is right.mode
        and left.target_category == right.target_category
    )


def _member_payload(row: ReviewRow) -> dict[str, str | None]:
    return {
        "row_id": row.row_id,
        "display_name": row.display_name or "",
        "source_unit": row.unit,
        "quantity": _money(row.quantity),
        "cost": _money(row.cost),
    }


def _money(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
