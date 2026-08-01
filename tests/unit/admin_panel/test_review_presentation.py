from types import SimpleNamespace

from report_processor.admin_panel.review_presentation import (
    context_record,
    group_context,
    manual_review_groups,
    suggestion_review_groups,
)


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


def test_member_context_includes_safe_quantity_and_cost() -> None:
    source = SimpleNamespace(
        work_name="Монтаж",
        unit="м",
        source_row=SimpleNamespace(remaining_quantity=3.5, total_cost=1200),
    )

    assert context_record([source], None, None) == {
        "work_name": "Монтаж",
        "source_unit": "м",
        "quantity": 3.5,
        "cost": 1200.0,
    }


def test_zero_source_totals_are_not_replaced_by_fallback_values() -> None:
    source = SimpleNamespace(
        work_name="Монтаж",
        unit="м",
        source_row=SimpleNamespace(
            remaining_quantity=0,
            period_quantity=9,
            total_cost=0,
            period_cost=99,
        ),
    )

    assert context_record([source], None, None)["quantity"] == 0.0
    assert context_record([source], None, None)["cost"] == 0.0


def test_group_aggregate_cost_deduplicates_identical_derived_costs() -> None:
    assert (
        group_context(
            [
                {"context": {"aggregate_cost": 1200}},
                {"context": {"aggregate_cost": 1200}},
            ]
        )["aggregate_cost"]
        == 1200.0
    )


def test_suggestion_group_exposes_every_candidate_that_may_be_resolved() -> None:
    suggestions = [
        {
            "suggestion_id": f"candidate-{index}",
            "target_ref": "target-a",
            "target_label": "Цель",
            "candidate_label": f"Работа {index}",
            "score": 0.5,
            "requires_manual_review": True,
        }
        for index in range(25)
    ]

    groups = suggestion_review_groups(suggestions, [])

    assert len(groups) == 1
    assert len(groups[0]["candidates"]) == 25
