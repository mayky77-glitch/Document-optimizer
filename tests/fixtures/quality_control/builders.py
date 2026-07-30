"""Compact builders for Block 14 quality-control engine tests."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from fixtures.calculation.builders import calculation_rule_set, calculation_source_row, match_result
from report_processor.calculation import calculate_matches
from report_processor.target_report.models import TargetNumericCell


def quality_rule_set(*, tolerance: Decimal = Decimal("0")) -> object:
    """Return an accepted rule set with exactly one tolerance authority."""

    rules = calculation_rule_set()
    return replace(rules, defaults=replace(rules.defaults, cost_tolerance_ratio=tolerance))


def calculated_match(
    *,
    result_id: str = "match-result-a",
    target_row_id: str = "target-a",
    source_row_id: str = "source-a:17",
    quantity: Decimal | None = Decimal("2.50"),
    cost: Decimal | None = Decimal("25.00"),
    target_cost: Decimal | None = Decimal("25.00"),
    target_unit: str | None = "m",
    writable: bool = True,
) -> object:
    """Create one selected match whose target values can expose quality signals."""

    source = calculation_source_row(source_row_id, quantity=quantity, cost=cost)
    match = match_result(
        source,
        result_id=result_id,
        candidate_id=f"candidate-{result_id}",
        target_row_id=target_row_id,
        target_unit=target_unit,
    )
    numeric = None
    if target_cost is not None:
        numeric = TargetNumericCell(target_cost, str(target_cost), "VALUE", "OK")
    target = replace(match.target_row, selected_cost=numeric, writable=writable)
    candidate = replace(
        match.selected_candidate,
        target_provenance={
            "target_source_id": "target",
            "sheet_name": target.sheet_name,
            "row_number": target.row_number,
            "target_row_id": target_row_id,
        },
    )
    return replace(match, target_row=target, selected_candidate=candidate, candidates=(candidate,))


def calculated_result(match: object, rules: object | None = None) -> object:
    """Calculate one result through the accepted Block 13 public API."""

    return calculate_matches((match,), rules or quality_rule_set())[0]
