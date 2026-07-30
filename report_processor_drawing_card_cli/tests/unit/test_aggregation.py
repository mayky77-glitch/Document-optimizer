from decimal import Decimal

from report_processor.drawing_card.aggregation.aggregator import aggregate_rows
from report_processor.drawing_card.models import (
    DrawingSourceLocation,
    DrawingSourceRow,
    MatchDecision,
    TargetWorkCategory,
)


def _source(row_id: str, unit: str, qty: str | None, cost: str | None) -> DrawingSourceRow:
    return DrawingSourceRow(
        row_id=row_id,
        location=DrawingSourceLocation("f", "x.xlsx", "ВиСР", 1, ("A1",)),
        object_index_raw="0906",
        drawing_code_raw="CODE",
        work_name_raw="Монтаж металлоконструкций",
        unit_raw=unit,
        remaining_quantity=None if qty is None else Decimal(qty),
        remaining_total_cost=None if cost is None else Decimal(cost),
        formula_values=(),
        cached_values=(),
        source_document_type="visr",
        source_period=None,
        source_revision=None,
        status="OK",
        warnings=(),
    )


def _decision(row_id: str, q: str, c: str) -> MatchDecision:
    return MatchDecision(
        row_id=row_id,
        category=TargetWorkCategory.METAL_STRUCTURES,
        quantity_decision=q,
        cost_decision=c,
        quantity_rule_id="q-rule",
        cost_rule_id="c-rule",
        quantity_confidence=0.9,
        cost_confidence=0.8,
        matching_strategy="test",
        evidence_ids=(),
        reason="test",
        requires_manual_review=False,
        status="OK",
        warnings=(),
    )


def test_quantity_and_cost_can_come_from_different_rows() -> None:
    rows = [_source("q", "т", "3", None), _source("c", "руб", None, "100")]
    decisions = [_decision("q", "include", "exclude"), _decision("c", "exclude", "include")]
    result = aggregate_rows(rows, decisions, drawing_code_mode="preserve_group", strict=True)[0]
    assert result.quantity == Decimal("3")
    assert result.total_cost == Decimal("100")
    assert result.quantity_rows == ("q",)
    assert result.cost_rows == ("c",)
    assert result.quantity_matching_strategies == ("test",)
    assert result.cost_matching_strategies == ("test",)


def test_incompatible_quantity_units_are_not_summed() -> None:
    rows = [_source("a", "т", "3", None), _source("b", "м", "4", None)]
    decisions = [_decision("a", "include", "exclude"), _decision("b", "include", "exclude")]
    result = aggregate_rows(rows, decisions, drawing_code_mode="preserve_group", strict=True)[0]
    assert result.quantity is None
    assert result.requires_manual_review
