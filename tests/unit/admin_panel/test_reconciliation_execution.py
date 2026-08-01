from decimal import Decimal
from types import SimpleNamespace

from report_processor.admin_panel.reconciliation_execution import _feedback_decisions
from report_processor.reconciliation_review import (
    FeedbackRecord,
    ReviewAction,
    ReviewMode,
    ReviewRow,
    build_review_groups,
)


def test_feedback_decisions_keep_row_feedback_over_group_feedback() -> None:
    first = ReviewRow("source-a:1", "Монтаж трубы", "м", Decimal("1"), Decimal("2"))
    second = ReviewRow("source-b:1", "Монтаж трубы", "м", Decimal("1"), Decimal("2"))
    (group,) = build_review_groups((first, second))
    artifacts = SimpleNamespace(review_rows=(first, second), review_groups=(group,))
    feedback = (
        FeedbackRecord(
            group.normalized_name or "",
            group.normalized_unit,
            ReviewAction.ACCEPT,
            "target-1",
            ReviewMode.QUANTITY_COST,
            1,
        ),
        FeedbackRecord("Монтаж трубы", "м", ReviewAction.REJECT, sequence=2),
    )

    decisions = _feedback_decisions(artifacts, feedback)

    assert {decision.row_id for decision in decisions if decision.row_id} == {
        "source-a:1",
        "source-b:1",
    }
    assert all(decision.action is ReviewAction.REJECT for decision in decisions if decision.row_id)
