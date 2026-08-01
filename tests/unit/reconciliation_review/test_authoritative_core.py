from decimal import Decimal

from report_processor.reconciliation_review import (
    ReviewAction,
    ReviewDecision,
    ReviewMode,
    ReviewRow,
    apply_overrides,
    build_review_groups,
)


def _row(row_id: str, *, quantity: str = "2", cost: str = "10") -> ReviewRow:
    return ReviewRow(
        row_id=row_id,
        display_name="Монтаж трубы",
        unit="м",
        quantity=Decimal(quantity),
        cost=Decimal(cost),
    )


def test_two_source_rows_form_one_global_group_and_row_choice_wins() -> None:
    rows = (_row("source-a:1"), _row("source-b:1", quantity="3", cost="15"))
    (group,) = build_review_groups(rows)

    assert group.member_ids == ("source-a:1", "source-b:1")

    overrides = apply_overrides(
        rows,
        (group,),
        (
            ReviewDecision(
                action=ReviewAction.ACCEPT,
                mode=ReviewMode.QUANTITY_COST,
                target_category="target-1",
                group_id=group.group_id,
                version=group.version,
            ),
            ReviewDecision(
                action=ReviewAction.ACCEPT,
                mode=ReviewMode.COST_ONLY,
                target_category="target-2",
                row_id="source-b:1",
                version=group.version,
            ),
        ),
    )

    assert overrides["source-a:1"].candidate_inclusion == (True, True)
    assert overrides["source-a:1"].target_category == "target-1"
    assert overrides["source-b:1"].candidate_inclusion == (False, True)
    assert overrides["source-b:1"].target_category == "target-2"


def test_reject_removes_group_application_and_stale_group_version_is_rejected() -> None:
    rows = (_row("source-a:1"), _row("source-b:1"))
    (group,) = build_review_groups(rows)
    accepted = ReviewDecision(
        action=ReviewAction.ACCEPT,
        mode=ReviewMode.QUANTITY_COST,
        target_category="target-1",
        group_id=group.group_id,
        version=group.version,
    )
    rejected = ReviewDecision(
        action=ReviewAction.REJECT,
        row_id="source-a:1",
        version=group.version,
    )

    overrides = apply_overrides(rows, (group,), (accepted, rejected))

    assert set(overrides) == {"source-b:1"}

    stale = ReviewDecision(
        action=ReviewAction.REJECT,
        group_id=group.group_id,
        version="stale",
    )
    try:
        apply_overrides(rows, (group,), (stale,))
    except ValueError as error:
        assert str(error) == "decision version is stale"
    else:  # pragma: no cover - assertion makes stale writes a hard failure
        raise AssertionError("stale decision was accepted")
