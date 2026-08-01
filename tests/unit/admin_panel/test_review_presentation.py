from types import SimpleNamespace

from report_processor.admin_panel.review_presentation import context_record, manual_review_groups


def test_manual_group_keeps_members_server_side_by_default() -> None:
    groups = manual_review_groups(
        [
            {
                "discrepancy_id": "issue-1",
                "code": "AMBIGUOUS",
                "severity": "manual_review",
                "message": "Проверка",
                "context": {"work_name": "Монтаж"},
            }
        ],
        [],
    )

    assert groups[0]["count"] == 1
    assert "discrepancy_ids" not in groups[0]
    assert groups[0]["members"] == [{"title": "Монтаж", "context": {"work_name": "Монтаж"}}]


def test_context_falls_back_to_target_and_includes_match_confidence() -> None:
    match = SimpleNamespace(
        target_row=SimpleNamespace(stage="Цель", unit="шт"),
        explanation=(),
        selected_candidate=SimpleNamespace(confidence=0.88),
        candidates=(),
    )

    assert context_record([], match, None) == {
        "work_name": "Цель",
        "target_unit": "шт",
        "proposed_match": "Цель",
        "confidence": 0.88,
    }
