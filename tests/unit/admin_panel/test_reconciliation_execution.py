from decimal import Decimal
from types import SimpleNamespace

from report_processor.admin_panel.reconciliation_execution import _feedback_records, apply_review
from report_processor.reconciliation_review import (
    FeedbackRecord,
    ReviewAction,
    ReviewDecision,
    ReviewMode,
    ReviewRow,
    build_review_groups,
)


def test_feedback_records_restore_row_feedback_over_group_feedback() -> None:
    first = ReviewRow("source-a:1", "Монтаж трубы", "м", Decimal("1"), Decimal("2"))
    second = ReviewRow("source-b:1", "Монтаж трубы", "м", Decimal("1"), Decimal("2"))
    (group,) = build_review_groups((first, second))
    state = SimpleNamespace(
        groups={group.group_id: group},
        rows={first.row_id: first, second.row_id: second},
        group_decisions={
            group.group_id: ReviewDecision(
                ReviewAction.ACCEPT,
                ReviewMode.QUANTITY_COST,
                "target-1",
                group_id=group.group_id,
            )
        },
        row_decisions={
            second.row_id: ReviewDecision(
                ReviewAction.REJECT,
                row_id=second.row_id,
            )
        },
    )

    feedback = _feedback_records(state)

    assert feedback == (
        FeedbackRecord(
            group.normalized_name or "",
            group.normalized_unit,
            ReviewAction.ACCEPT,
            "target-1",
            ReviewMode.QUANTITY_COST,
            1,
        ),
        FeedbackRecord("монтаж трубы", "м", ReviewAction.REJECT, sequence=2),
    )


def test_apply_review_all_rejected_writes_unchanged_target_and_feedback(
    tmp_path, monkeypatch
) -> None:
    row = ReviewRow("source:1", "Монтаж трубы", "м", Decimal("1"), Decimal("2"))
    (group,) = build_review_groups((row,))
    rejected = SimpleNamespace(
        rows={row.row_id: row},
        groups={group.group_id: group},
        group_decisions={
            group.group_id: ReviewDecision(
                ReviewAction.REJECT,
                group_id=group.group_id,
            )
        },
        row_decisions={},
        core_decisions=lambda: (
            ReviewDecision(ReviewAction.REJECT, group_id=group.group_id, version=group.version),
        ),
    )
    job = SimpleNamespace(
        target=tmp_path / "target.xlsx",
        target_digest="target-digest",
        stage="13.1",
        directory=tmp_path,
        rules_path=None,
    )
    job.target.write_bytes(b"target")
    output = tmp_path / "result.xlsx"
    monkeypatch.setattr(
        "report_processor.admin_panel.reconciliation_execution.read_reconciliation_target",
        lambda *_args: (object(), ()),
    )
    monkeypatch.setattr(
        "report_processor.admin_panel.reconciliation_execution._sources",
        lambda _job: SimpleNamespace(rows=()),
    )
    monkeypatch.setattr(
        "report_processor.excel_writer.write_target_report",
        lambda *_args: SimpleNamespace(output_sha256="verified"),
    )

    written, feedback = apply_review(job, rejected)

    assert written == output
    assert feedback[0].action is ReviewAction.REJECT
