from decimal import Decimal

import pytest

from report_processor.admin_panel.reconciliation_state import ReconciliationReviewState
from report_processor.reconciliation_review import (
    ReviewAction,
    ReviewDecision,
    ReviewMode,
    ReviewRow,
    build_review_groups,
)


def _state() -> tuple[ReconciliationReviewState, str, str]:
    rows = {
        row_id: ReviewRow(row_id, "Монтаж трубы", "м", Decimal("1"), Decimal("2"))
        for row_id in ("source-a:1", "source-b:1")
    }
    (group,) = build_review_groups(rows.values())
    state = ReconciliationReviewState(
        rows=rows,
        groups={group.group_id: group},
        categories={"target-1": "Цель 1", "target-2": "Цель 2"},
        source_digests=("source-a", "source-b"),
        target_digest="target",
    )
    return state, group.group_id, group.member_ids[0]


def _accept_group(state: ReconciliationReviewState, group_id: str) -> str:
    version = state.group_snapshot()[0].version
    state.put_group(
        group_id,
        ReviewDecision(
            action=ReviewAction.ACCEPT,
            mode=ReviewMode.QUANTITY_COST,
            target_category="target-1",
            group_id=group_id,
            version=version,
        ),
    )
    return version


def test_stale_group_and_row_writes_leave_state_unmodified() -> None:
    state, group_id, row_id = _state()
    version = _accept_group(state, group_id)

    with pytest.raises(ValueError, match="stale"):
        state.put_row(
            row_id,
            ReviewDecision(action=ReviewAction.REJECT, row_id=row_id, version=version),
        )
    with pytest.raises(ValueError, match="stale"):
        state.delete_row(row_id, version)

    assert state.row_decisions == {}
    assert state.unresolved_row_ids() == ()


def test_row_override_changes_only_its_member_and_delete_restores_group_resolution() -> None:
    state, group_id, row_id = _state()
    _accept_group(state, group_id)
    row_version = state.group_snapshot()[0].version
    state.put_row(
        row_id,
        ReviewDecision(
            action=ReviewAction.ACCEPT,
            mode=ReviewMode.COST_ONLY,
            target_category="target-2",
            row_id=row_id,
            version=row_version,
        ),
    )

    decisions = {item.row_id or item.group_id: item for item in state.effective_decisions()}
    assert decisions[row_id].mode is ReviewMode.COST_ONLY
    assert decisions[group_id].target_category == "target-1"

    state.delete_row(row_id, state.group_snapshot()[0].version)
    assert state.row_decisions == {}
    assert state.unresolved_row_ids() == ()


def test_category_must_exist_for_every_group_member_but_row_override_is_scoped() -> None:
    state, group_id, row_id = _state()
    other_row_id = next(value for value in state.rows if value != row_id)
    state.available_categories = {
        row_id: frozenset({"target-1", "target-2"}),
        other_row_id: frozenset({"target-1"}),
    }
    version = state.group_snapshot()[0].version

    with pytest.raises(ValueError, match="unavailable for this group"):
        state.put_group(
            group_id,
            ReviewDecision(
                ReviewAction.ACCEPT,
                ReviewMode.QUANTITY_COST,
                "target-2",
                group_id=group_id,
                version=version,
            ),
        )

    state.put_row(
        row_id,
        ReviewDecision(
            ReviewAction.ACCEPT,
            ReviewMode.COST_ONLY,
            "target-2",
            row_id=row_id,
            version=version,
        ),
    )
    assert state.row_decisions[row_id].target_category == "target-2"
