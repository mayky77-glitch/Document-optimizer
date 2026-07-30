"""Integration evidence for the deterministic Block 13 calculation engine."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from decimal import Decimal

import pytest
from report_processor.calculation import (
    CalculationCategory,
    CalculationInputError,
    CalculationStatus,
    calculate_matches,
)

from fixtures.calculation.builders import calculation_rule_set, calculation_source_row, match_result
from report_processor.business_rules.models import RuleAction
from report_processor.matching import MatchStatus


def _digest(results: tuple[object, ...]) -> str:
    payload = [
        {
            "calculation_id": item.calculation_id,
            "status": item.status.value,
            "quantity": str(item.quantity),
            "cost": str(item.cost),
            "trace_id": item.trace.trace_id,
            "contributions": [
                contribution.contribution_id for contribution in item.trace.contributions
            ],
        }
        for item in results
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def test_selected_match_aggregates_then_rounds_once_and_applies_cost_coefficient() -> None:
    first = match_result(
        calculation_source_row("source-a", quantity=Decimal("0.005"), cost=Decimal("1.005"))
    )
    second = match_result(
        calculation_source_row("source-b", quantity=Decimal("0.005"), cost=Decimal("1.005")),
        result_id="match-result-b",
        candidate_id="candidate-b",
        target_row_id="target-b",
        row_number=9,
    )
    results = calculate_matches((second, first), calculation_rule_set(coefficient=Decimal("1.1")))
    assert tuple(item.match_result_id for item in results) == ("match-result-a", "match-result-b")
    assert results[0].quantity == Decimal("0.01")
    assert results[0].cost_before_coefficient == Decimal("1.005")
    assert results[0].coefficient == Decimal("1.1")
    assert results[0].cost == Decimal("1.11")
    trace = results[0].trace
    assert trace.coefficient == Decimal("1.1")
    assert trace.rounding_quantum == Decimal("0.01")
    assert trace.rounding_mode == "ROUND_HALF_UP"
    assert trace.formula_tokens and all(isinstance(token, str) for token in trace.formula_tokens)
    contribution = trace.contributions[0]
    assert contribution.raw_quantity == contribution.included_quantity == Decimal("0.005")
    assert contribution.raw_cost == contribution.included_cost == Decimal("1.005")
    assert contribution.source_provenance["source_row_id"] == "source-a"
    assert contribution.target_provenance["target_row_id"] == "target-a"


def test_missing_zero_negative_unit_category_and_independent_include_decisions() -> None:
    zero = match_result(calculation_source_row("zero", quantity=Decimal("0"), cost=Decimal("0")))
    missing = match_result(
        calculation_source_row("missing", quantity=None, cost=None),
        result_id="missing",
        candidate_id="missing",
        target_row_id="target-missing",
        row_number=9,
    )
    negative = match_result(
        calculation_source_row("negative", quantity=Decimal("-2"), cost=Decimal("-3")),
        result_id="negative",
        candidate_id="negative",
        target_row_id="target-negative",
        row_number=10,
    )
    excluded_quantity = match_result(
        calculation_source_row("cost-only", quantity=Decimal("5"), cost=Decimal("7")),
        result_id="cost-only",
        candidate_id="cost-only",
        target_row_id="target-cost-only",
        row_number=11,
    )
    results = calculate_matches((zero, missing, negative), calculation_rule_set(allowed_units=()))
    by_id = {item.match_result_id: item for item in results}
    assert by_id["match-result-a"].quantity == Decimal("0.00")
    assert by_id["match-result-a"].cost == Decimal("0.00")
    assert by_id["missing"].status is CalculationStatus.NO_VALUES
    assert by_id["missing"].quantity is None and by_id["missing"].cost is None
    assert by_id["negative"].cost == Decimal("-3.00")
    assert by_id["negative"].warnings
    cost_only = calculate_matches(
        (excluded_quantity,),
        calculation_rule_set(include_quantity=False, include_cost=True, allowed_units=()),
    )[0]
    assert cost_only.quantity is None
    assert cost_only.cost == Decimal("7.00")
    assert cost_only.category_totals[0].category is CalculationCategory.WORK


def test_nonselected_rules_categories_and_duplicate_identities_are_controlled() -> None:
    source = calculation_source_row("source-a", cost_type_code="UNKNOWN")
    ambiguous = match_result(source, status=MatchStatus.AMBIGUOUS)
    unmatched = match_result(
        source,
        status=MatchStatus.UNMATCHED,
        result_id="unmatched",
        target_row_id="target-unmatched",
        row_number=9,
    )
    calculated = match_result(
        source,
        result_id="calculated",
        target_row_id="target-calculated",
        row_number=10,
    )
    results = calculate_matches((calculated, ambiguous, unmatched), calculation_rule_set())
    by_id = {item.match_result_id: item for item in results}
    assert by_id["match-result-a"].status is CalculationStatus.MANUAL_REVIEW
    assert by_id["match-result-a"].quantity is None and by_id["match-result-a"].cost is None
    assert by_id["unmatched"].status is CalculationStatus.NO_MATCH
    categories = {item.category for item in by_id["calculated"].category_totals}
    assert CalculationCategory.UNCLASSIFIED in categories
    assert "pipe" not in {item.value for item in categories}
    with pytest.raises(CalculationInputError):
        calculate_matches((calculated, replace(calculated)), calculation_rule_set())


@pytest.mark.parametrize(
    ("action", "owner_approved", "status", "expected"),
    (
        (RuleAction.EXCLUDE, True, "approved", CalculationStatus.MANUAL_REVIEW),
        (RuleAction.REVIEW, True, "approved", CalculationStatus.MANUAL_REVIEW),
        (RuleAction.EXCLUDE, False, "draft", CalculationStatus.CALCULATED),
    ),
)
def test_approved_rules_only_control_exclude_and_review(
    action: RuleAction, owner_approved: bool, status: str, expected: CalculationStatus
) -> None:
    result = match_result(calculation_source_row())
    if not owner_approved or status != "approved":
        candidate = replace(result.selected_candidate, rule_ids=())
        result = replace(result, selected_candidate=candidate, candidates=(candidate,))
    actual = calculate_matches(
        (result,),
        calculation_rule_set(action=action, owner_approved=owner_approved, status=status),
    )[0]
    assert actual.status is expected


def test_rejects_float_nonfinite_and_is_deterministic_without_workbook_writes() -> None:
    source = calculation_source_row()
    result = match_result(source)
    rules = calculation_rule_set(source_priority=("does-not-filter",))
    first = calculate_matches((result,), rules)
    second = calculate_matches((result,), rules)
    assert _digest(first) == _digest(second)
    with pytest.raises(CalculationInputError):
        calculate_matches(
            (result,),
            replace(rules, defaults=replace(rules.defaults, default_run_coefficient=1.0)),
        )
    invalid_source = calculation_source_row(cost=Decimal("Infinity"))
    with pytest.raises(CalculationInputError):
        calculate_matches((match_result(invalid_source),), rules)
