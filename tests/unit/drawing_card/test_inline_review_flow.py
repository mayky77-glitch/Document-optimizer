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
from report_processor.drawing_card.workflow import _aggregate_unit_mismatch_reviews

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


def test_late_aggregate_unit_mismatch_becomes_actionable_row_review() -> None:
    metre_row = _row()
    item_row = replace(_row(), row_id="review-row-2", unit_raw="шт")
    metre_decision = _manual_decision("approve")
    item_decision = replace(metre_decision, row_id=item_row.row_id)
    rows = [metre_row, item_row]
    decisions = [metre_decision, item_decision]
    aggregated = aggregate_rows(rows, decisions, drawing_code_mode="strict", strict=True)

    review_rows, review_decisions = _aggregate_unit_mismatch_reviews(rows, decisions, aggregated)

    assert aggregated[0].status == Status.UNIT_MISMATCH
    assert {row.row_id for row in review_rows} == {"review-row-1", "review-row-2"}
    assert {decision.row_id for decision in review_decisions} == {
        "review-row-1",
        "review-row-2",
    }
    assert all(decision.quantity_decision == "review" for decision in review_decisions)
    assert all(decision.cost_decision == "include" for decision in review_decisions)
    assert all(decision.requires_manual_review for decision in review_decisions)
    assert all(Status.UNIT_MISMATCH in decision.warnings for decision in review_decisions)


def test_contract_and_performed_values_follow_the_same_included_source_sets() -> None:
    quantity_row = replace(
        _row(),
        row_id="quantity-row",
        remaining_quantity=Decimal("12"),
        remaining_total_cost=None,
        contract_quantity=Decimal("20"),
        performed_quantity=Decimal("8"),
        contract_total_cost=Decimal("900"),
        performed_total_cost=Decimal("700"),
    )
    cost_row = replace(
        _row(),
        row_id="cost-row",
        work_name_raw="Другая строка той же категории",
        remaining_quantity=None,
        remaining_total_cost=Decimal("3500"),
        contract_quantity=Decimal("30"),
        performed_quantity=Decimal("15"),
        contract_total_cost=Decimal("5000"),
        performed_total_cost=Decimal("6000"),
    )
    quantity_only = MatchDecision(
        row_id="quantity-row",
        category=TargetWorkCategory.LOW_CURRENT_CABLE,
        quantity_decision="include",
        cost_decision="exclude",
        quantity_rule_id="quantity-rule",
        cost_rule_id=None,
        quantity_confidence=1.0,
        cost_confidence=None,
        matching_strategy="test",
        evidence_ids=(),
        reason="test",
        requires_manual_review=False,
        status=Status.OK,
        warnings=(),
    )
    cost_only = MatchDecision(
        row_id="cost-row",
        category=TargetWorkCategory.LOW_CURRENT_CABLE,
        quantity_decision="exclude",
        cost_decision="include",
        quantity_rule_id=None,
        cost_rule_id="cost-rule",
        quantity_confidence=None,
        cost_confidence=1.0,
        matching_strategy="test",
        evidence_ids=(),
        reason="test",
        requires_manual_review=False,
        status=Status.OK,
        warnings=(),
    )

    result = aggregate_rows(
        [quantity_row, cost_row],
        [quantity_only, cost_only],
        drawing_code_mode="strict",
        strict=True,
    )[0]

    assert result.quantity_rows == ("quantity-row",)
    assert result.cost_rows == ("cost-row",)
    assert (result.quantity, result.contract_quantity, result.performed_quantity) == (
        Decimal("12"),
        Decimal("20"),
        Decimal("8"),
    )
    assert (result.total_cost, result.contract_total_cost, result.performed_total_cost) == (
        Decimal("3500"),
        Decimal("5000"),
        Decimal("6000"),
    )


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
    ("action", "category", "quantity", "cost", "requires_manual_review"),
    (
        ("approve", TargetWorkCategory.LOW_CURRENT_CABLE, "include", "include", False),
        ("change_category", TargetWorkCategory.CONCRETE_WORKS, "review", "include", True),
        ("cost_only", TargetWorkCategory.LOW_CURRENT_CABLE, "exclude", "include", False),
        ("reject", None, "exclude", "exclude", False),
        ("skip", None, "exclude", "exclude", False),
    ),
)
def test_inline_feedback_replays_every_explicit_action_without_manual_review(
    tmp_path: Path,
    action: str,
    category: TargetWorkCategory | None,
    quantity: str,
    cost: str,
    requires_manual_review: bool,
) -> None:
    feedback = tmp_path / "review-feedback.jsonl"
    append_feedback(
        feedback,
        {"review-row-1": _row()},
        {"review-row-1": ReviewApproval("review-row-1", action, category)},
    )

    repeated = replace(_row(), row_id="same-text-next-run")
    decision = DrawingRowMatcher(RULES, load_confirmed_examples(feedback), rag_mode="off").match(
        repeated
    )

    assert decision.category is category
    assert (decision.quantity_decision, decision.cost_decision) == (quantity, cost)
    assert decision.requires_manual_review is requires_manual_review
    if requires_manual_review:
        assert decision.matching_strategy == "review"
        assert Status.UNIT_MISMATCH in decision.warnings
    else:
        assert decision.matching_strategy == "confirmed_dictionary"


def test_exact_feedback_cannot_replay_quantity_against_current_category_unit_policy() -> None:
    row = replace(
        _row(),
        unit_raw="компл",
        work_name_raw="Монтаж технологической ЗРА",
    )
    example = ConfirmedExample(
        example_id="feedback-incompatible-category-unit",
        source_text=row.work_name_raw or "",
        normalized_text="монтаж технологической зра",
        category=TargetWorkCategory.TT_VALVES_INSTALLATION,
        quantity_decision="include",
        cost_decision="include",
        unit="компл",
        source_type="ks6a",
        confirmed_by="inline-review",
        rule_version="ReviewFeedbackStore-1.0",
    )

    decision = DrawingRowMatcher(RULES, (example,), rag_mode="off").match(row)

    assert decision.category is TargetWorkCategory.TT_VALVES_INSTALLATION
    assert (decision.quantity_decision, decision.cost_decision) == ("review", "include")
    assert decision.matching_strategy == "review"
    assert decision.requires_manual_review is True
    assert Status.UNIT_MISMATCH in decision.warnings


def test_exact_cost_only_feedback_remains_replayable_across_category_unit_mismatch() -> None:
    row = replace(
        _row(),
        unit_raw="компл",
        work_name_raw="Монтаж технологической ЗРА",
    )
    example = ConfirmedExample(
        example_id="feedback-cost-only-incompatible-category-unit",
        source_text=row.work_name_raw or "",
        normalized_text="монтаж технологической зра",
        category=TargetWorkCategory.TT_VALVES_INSTALLATION,
        quantity_decision="exclude",
        cost_decision="include",
        unit="компл",
        source_type="ks6a",
        confirmed_by="inline-review",
        rule_version="ReviewFeedbackStore-1.0",
    )

    decision = DrawingRowMatcher(RULES, (example,), rag_mode="off").match(row)

    assert decision.category is TargetWorkCategory.TT_VALVES_INSTALLATION
    assert (decision.quantity_decision, decision.cost_decision) == ("exclude", "include")
    assert decision.matching_strategy == "confirmed_dictionary"
    assert decision.requires_manual_review is False
