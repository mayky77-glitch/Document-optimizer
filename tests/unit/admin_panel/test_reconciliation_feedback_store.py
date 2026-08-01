from report_processor.admin_panel.reconciliation_feedback_store import ReconciliationFeedbackStore
from report_processor.reconciliation_review import (
    FeedbackRecord,
    ReviewAction,
    ReviewMode,
    ReviewRow,
    build_review_groups,
    feedback_for_group,
    latest_feedback,
    suppress_resolved_groups,
)


def test_feedback_is_target_scoped_latest_wins_and_suppresses_only_same_target(tmp_path) -> None:
    store = ReconciliationFeedbackStore(tmp_path)
    first = FeedbackRecord("Монтаж трубы", "м", ReviewAction.REJECT)
    latest = FeedbackRecord(
        "монтаж   трубы",
        "М.",
        ReviewAction.ACCEPT,
        target_category="target-1",
        mode=ReviewMode.COST_ONLY,
    )
    store.persist("target-a", (first, latest))

    records = store.records("target-a")
    row = ReviewRow("source:1", "Монтаж трубы", "м", None, None)
    (group,) = build_review_groups((row,))

    resolved = feedback_for_group(group, records)
    assert resolved is not None and resolved.action is ReviewAction.ACCEPT
    assert resolved.mode is ReviewMode.COST_ONLY
    assert suppress_resolved_groups((group,), records) == ()
    assert suppress_resolved_groups((group,), store.records("target-b")) == (group,)


def test_exact_row_feedback_wins_over_group_key_at_latest_sequence() -> None:
    group = FeedbackRecord(
        "Монтаж трубы", "м", ReviewAction.ACCEPT, "target-1", ReviewMode.QUANTITY_COST, 1
    )
    row = FeedbackRecord("Монтаж трубы", "м", ReviewAction.REJECT, sequence=2)

    latest = latest_feedback((group, row))

    assert next(iter(latest.values())).action is ReviewAction.REJECT
