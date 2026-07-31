"""Regression contract for explicit inline-review decisions."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from report_processor.drawing_card.aggregation import aggregate_rows
from report_processor.drawing_card.matching.matcher import DrawingRowMatcher, ReviewApproval
from report_processor.drawing_card.models import (
    DrawingSourceLocation,
    DrawingSourceRow,
    MatchDecision,
    TargetWorkCategory,
)
from report_processor.drawing_card.review.inline import append_feedback
from report_processor.drawing_card.statuses import Status


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
