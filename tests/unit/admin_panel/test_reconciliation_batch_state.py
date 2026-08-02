from decimal import Decimal

import pytest

from report_processor.admin_panel.reconciliation_batch_presentation import (
    reconciliation_batch_payload,
)
from report_processor.admin_panel.reconciliation_batch_store import ReconciliationBatchStore
from report_processor.admin_panel.reconciliation_state import (
    BatchReviewDecision,
    ReconciliationReviewState,
)
from report_processor.reconciliation_grouping import (
    PackageVersionContext,
    build_reconciliation_packages,
)
from report_processor.reconciliation_review import (
    ReviewAction,
    ReviewDecision,
    ReviewMode,
    ReviewRow,
    build_review_groups,
)


def _state() -> ReconciliationReviewState:
    rows = {
        row_id: ReviewRow(
            row_id,
            "Монтаж силового кабеля",
            "м",
            Decimal("1"),
            Decimal("2"),
            "target-1",
        )
        for row_id in ("row-a", "row-b")
    }
    groups = build_review_groups(rows.values())
    grouping = build_reconciliation_packages(
        rows.values(),
        groups,
        version_context=PackageVersionContext(("source",), "target", "catalog"),
    )
    return ReconciliationReviewState(
        rows=rows,
        groups={group.group_id: group for group in groups},
        categories={"target-1": "Целевая категория", "target-2": "Другая категория"},
        source_digests=("source",),
        target_digest="target",
        grouping=grouping,
    )


def test_package_family_group_row_precedence_and_undo() -> None:
    state = _state()
    package = state.grouping.packages[0]
    family = state.grouping.families[0]
    group = next(iter(state.groups.values()))
    row_id = group.member_ids[0]

    state.put_package(
        package.package_id,
        BatchReviewDecision(
            ReviewAction.ACCEPT, ReviewMode.QUANTITY_COST, "target-1", package.version
        ),
    )
    state.put_family(
        family.family_id,
        BatchReviewDecision(ReviewAction.REJECT, version=family.version),
    )
    group_version = state.group_snapshot()[0].version
    state.put_group(
        group.group_id,
        ReviewDecision(
            ReviewAction.ACCEPT,
            ReviewMode.COST_ONLY,
            "target-2",
            group.group_id,
            version=group_version,
        ),
    )
    row_version = state.group_snapshot()[0].version
    state.put_row(row_id, ReviewDecision(ReviewAction.REJECT, row_id=row_id, version=row_version))

    effective = {item.row_id or item.group_id: item for item in state.core_decisions()}
    assert effective[group.group_id].target_category == "target-2"
    assert effective[row_id].action is ReviewAction.REJECT

    state.undo()
    assert row_id not in state.row_decisions
    assert state.last_action == "Последнее решение отменено."


def test_stale_safe_package_is_rejected_before_mutation() -> None:
    state = _state()
    package = state.grouping.packages[0]

    with pytest.raises(ValueError, match="stale"):
        state.put_package(
            package.package_id,
            BatchReviewDecision(ReviewAction.ACCEPT, ReviewMode.COST_ONLY, "target-1", "old"),
        )

    assert state.package_decisions == {}


def test_autosave_restore_and_mass_accept_match_sequential_decision(tmp_path) -> None:
    mass = _state()
    package = mass.grouping.packages[0]
    store = ReconciliationBatchStore(tmp_path)
    mass.set_autosave(store.save)
    mass.accept_safe_packages(((package.package_id, package.version),))

    restored = _state()
    assert store.restore(restored) is True
    sequential = _state()
    sequential.put_package(
        package.package_id,
        BatchReviewDecision(
            ReviewAction.ACCEPT,
            ReviewMode(package.package_key[1]),
            package.package_key[0],
            package.version,
        ),
    )

    assert restored.core_decisions() == mass.core_decisions() == sequential.core_decisions()


def test_payload_is_private_and_uses_two_decimal_strings() -> None:
    state = _state()
    payload = reconciliation_batch_payload(state)

    package = payload["review_packages"][0]
    assert package["quantity"] == "2.00" and package["cost"] == "4.00"
    assert package["row_count"] == "2.00"
    serialized = repr(payload)
    assert all(value not in serialized for value in ("digest", "path", "warning", "confidence"))
