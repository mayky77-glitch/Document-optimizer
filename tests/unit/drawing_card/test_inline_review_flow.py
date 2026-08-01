"""Regression contract for explicit inline-review decisions."""

from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from report_processor.drawing_card.aggregation import aggregate_rows
from report_processor.drawing_card.config import load_rules
from report_processor.drawing_card.matching.examples import (
    ConfirmedExample,
    exact_example_match,
    has_exact_example_conflict,
    load_confirmed_examples,
)
from report_processor.drawing_card.matching.matcher import DrawingRowMatcher, ReviewApproval
from report_processor.drawing_card.models import (
    DrawingSourceLocation,
    DrawingSourceRow,
    MatchDecision,
    TargetWorkCategory,
)
from report_processor.drawing_card.review.inline import append_feedback
from report_processor.drawing_card.statuses import Status

RULES = load_rules(
    Path(__file__).parents[3]
    / "src"
    / "report_processor"
    / "drawing_card"
    / "resources"
    / "rules.json"
)


def _row() -> DrawingSourceRow:
    return DrawingSourceRow(
        row_id="review-row-1",
        location=DrawingSourceLocation(
            file_id="source-1",
            filename="private.xlsx",
            sheet_name="Лист1",
            row_number=12,
            coordinates=("A12",),
        ),
        object_index_raw="1006",
        drawing_code_raw="А-001",
        work_name_raw="Монтаж контрольного кабеля",
        unit_raw="м",
        remaining_quantity=Decimal("12"),
        remaining_total_cost=Decimal("3500"),
        formula_values=(),
        cached_values=(),
        source_document_type="ks6a",
        source_period="2026-07",
        source_revision=None,
        status=Status.OK,
        warnings=(),
    )


def _manual_decision(action: str) -> MatchDecision:
    matcher = object.__new__(DrawingRowMatcher)
    matcher.approvals = {
        "review-row-1": ReviewApproval(
            row_id="review-row-1",
            action=action,
            category=TargetWorkCategory.LOW_CURRENT_CABLE,
        )
    }
    decision = matcher._approved_decision(_row())
    assert decision is not None
    return decision


def test_cost_only_keeps_category_and_cost_but_writes_explicit_zero_quantity() -> None:
    row = _row()
    decision = _manual_decision("cost_only")

    aggregated = aggregate_rows([row], [decision], drawing_code_mode="strict", strict=True)

    assert decision.category is TargetWorkCategory.LOW_CURRENT_CABLE
    assert decision.quantity_decision == "exclude"
    assert decision.cost_decision == "include"
    assert len(aggregated) == 1
    assert aggregated[0].category is TargetWorkCategory.LOW_CURRENT_CABLE
    assert aggregated[0].quantity == Decimal("0")
    assert aggregated[0].total_cost == Decimal("3500")
    assert aggregated[0].quantity_rows == ()
    assert aggregated[0].cost_rows == ("review-row-1",)


def test_approve_includes_both_quantity_and_cost() -> None:
    row = _row()
    decision = _manual_decision("approve")

    aggregated = aggregate_rows([row], [decision], drawing_code_mode="strict", strict=True)

    assert decision.quantity_decision == "include"
    assert decision.cost_decision == "include"
    assert aggregated[0].quantity == Decimal("12")
    assert aggregated[0].total_cost == Decimal("3500")


def test_cost_only_feedback_remembers_category_with_quantity_excluded(tmp_path: Path) -> None:
    feedback = tmp_path / "review-feedback.jsonl"
    approval = ReviewApproval(
        row_id="review-row-1",
        action="cost_only",
        category=TargetWorkCategory.LOW_CURRENT_CABLE,
    )

    append_feedback(feedback, {"review-row-1": _row()}, {"review-row-1": approval})

    record = json.loads(feedback.read_text(encoding="utf-8"))
    assert record["category"] == "low_current_cable"
    assert record["quantity_decision"] == "exclude"
    assert record["cost_decision"] == "include"


def test_reject_feedback_is_exact_unit_scoped_and_not_a_category_prediction(tmp_path: Path) -> None:
    feedback = tmp_path / "review-feedback.jsonl"
    rejection = ReviewApproval(row_id="review-row-1", action="reject", category=None)

    append_feedback(feedback, {"review-row-1": _row()}, {"review-row-1": rejection})

    record = json.loads(feedback.read_text(encoding="utf-8"))
    assert record["category"] is None
    assert (record["quantity_decision"], record["cost_decision"]) == ("exclude", "exclude")
    examples = (
        ConfirmedExample(
            example_id=record["example_id"],
            source_text=record["source_text"],
            normalized_text=record["normalized_text"],
            category=None,
            quantity_decision="exclude",
            cost_decision="exclude",
            unit=record["unit"],
            source_type=None,
            confirmed_by="inline-review",
            rule_version="ReviewFeedbackStore-1.0",
        ),
    )
    text = _row().work_name_raw or ""
    assert exact_example_match(text, examples, unit="шт", source_type=None) is None
    assert exact_example_match(text, examples, unit="м", source_type=None) == examples[0]


def test_latest_local_feedback_overrides_an_older_local_decision_and_bundled_example(
    tmp_path: Path,
) -> None:
    feedback = tmp_path / "review-feedback.jsonl"
    base = ConfirmedExample(
        example_id="bundled-example",
        source_text="Монтаж контрольного кабеля",
        normalized_text="монтаж контрольного кабеля",
        category=TargetWorkCategory.LOW_CURRENT_CABLE,
        quantity_decision="include",
        cost_decision="include",
        unit="м",
        source_type=None,
        confirmed_by="bundled",
        rule_version="1",
    )
    append_feedback(
        feedback,
        {"review-row-1": _row()},
        {
            "review-row-1": ReviewApproval(
                "review-row-1", "approve", TargetWorkCategory.LOW_CURRENT_CABLE
            )
        },
    )
    append_feedback(
        feedback,
        {"review-row-1": _row()},
        {"review-row-1": ReviewApproval("review-row-1", "reject", None)},
    )
    examples = (base, *load_confirmed_examples(feedback))
    decision = DrawingRowMatcher(RULES, examples, rag_mode="off").match(_row())

    assert feedback.read_text(encoding="utf-8").count("\n") == 1
    assert has_exact_example_conflict(base.source_text, examples, unit="м") is False
    assert decision.category is None
    assert (decision.quantity_decision, decision.cost_decision) == ("exclude", "exclude")
    assert decision.requires_manual_review is False


@pytest.mark.parametrize(
    ("action", "category", "quantity", "cost"),
    (
        ("approve", TargetWorkCategory.LOW_CURRENT_CABLE, "include", "include"),
        ("change_category", TargetWorkCategory.CONCRETE_WORKS, "include", "include"),
        ("cost_only", TargetWorkCategory.LOW_CURRENT_CABLE, "exclude", "include"),
        ("reject", None, "exclude", "exclude"),
        ("skip", None, "exclude", "exclude"),
    ),
)
def test_inline_feedback_replays_every_explicit_action_without_manual_review(
    tmp_path: Path,
    action: str,
    category: TargetWorkCategory | None,
    quantity: str,
    cost: str,
) -> None:
    feedback = tmp_path / "review-feedback.jsonl"
    append_feedback(
        feedback,
        {"review-row-1": _row()},
        {"review-row-1": ReviewApproval("review-row-1", action, category)},
    )

    repeated = replace(_row(), row_id="same-text-next-run")
    decision = DrawingRowMatcher(
        RULES, load_confirmed_examples(feedback), rag_mode="off"
    ).match(repeated)

    assert decision.category is category
    assert (decision.quantity_decision, decision.cost_decision) == (quantity, cost)
    assert decision.matching_strategy == "confirmed_dictionary"
    assert decision.requires_manual_review is False
