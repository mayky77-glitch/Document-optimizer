"""Decision, consistency, and deterministic evidence for Block 14."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from report_processor.quality_control import QualityDecision, evaluate_quality_control

from fixtures.quality_control.builders import calculated_match, calculated_result, quality_rule_set
from report_processor.calculation import CalculationStatus
from report_processor.matching import MatchStatus
from report_processor.target_report.models import TargetNumericCell


def _codes(report: object) -> set[str]:
    return {issue.code for issue in report.issues}


def test_decision_precedence_covers_all_four_write_outcomes() -> None:
    rules = quality_rule_set()
    clean_match = calculated_match()
    clean = calculated_result(clean_match, rules)
    clean_report = evaluate_quality_control((clean_match,), (clean,), rules)
    assert clean_report.decision is QualityDecision.ALLOW_WRITE

    warning_match = calculated_match(
        quantity=Decimal("-2"), cost=Decimal("-3"), target_cost=Decimal("-3")
    )
    warning = calculated_result(warning_match, rules)
    assert warning.status is CalculationStatus.CALCULATED_WITH_WARNINGS
    assert (
        evaluate_quality_control((warning_match,), (warning,), rules).decision
        is QualityDecision.ALLOW_WRITE_WITH_WARNINGS
    )

    unmatched_match = replace(
        clean_match,
        status=MatchStatus.UNMATCHED,
        selected_candidate=None,
        target_row=replace(clean_match.target_row, selected_cost=None),
    )
    unmatched = calculated_result(unmatched_match, rules)
    assert (
        evaluate_quality_control((unmatched_match,), (unmatched,), rules).decision
        is QualityDecision.REQUIRE_MANUAL_REVIEW
    )

    blocked_match = calculated_match(writable=False)
    blocked = calculated_result(blocked_match, rules)
    report = evaluate_quality_control((blocked_match,), (blocked,), rules)
    assert report.decision is QualityDecision.BLOCK_WRITE
    assert "TARGET_NOT_WRITABLE" in _codes(report)

    combined = evaluate_quality_control(
        (blocked_match, unmatched_match), (blocked, unmatched), rules
    )
    assert combined.decision is QualityDecision.BLOCK_WRITE


def test_formula_cache_and_provenance_are_blocking_without_sensitive_values() -> None:
    rules = quality_rule_set()
    match = calculated_match()
    formula_cell = TargetNumericCell(Decimal("25"), "25", "FORMULA_WITHOUT_CACHE", "OK")
    target = replace(match.target_row, selected_cost=formula_cell)
    candidate = replace(
        match.selected_candidate, target_provenance={"target_row_id": match.target_row_id}
    )
    formula_match = replace(
        match, target_row=target, selected_candidate=candidate, candidates=(candidate,)
    )
    calculation = calculated_result(formula_match, rules)
    report = evaluate_quality_control((formula_match,), (calculation,), rules)
    assert report.decision is QualityDecision.BLOCK_WRITE
    assert {"FORMULA_WITHOUT_CACHE", "MISSING_PROVENANCE"} <= _codes(report)
    assert all(
        "25" not in str(issue.evidence) and "=" not in str(issue.evidence)
        for issue in report.issues
    )

    excel_error = replace(
        match.target_row,
        selected_cost=TargetNumericCell(None, None, "VALUE", "EXCEL_ERROR"),
    )
    bad_match = replace(match, target_row=excel_error)
    bad_calculation = calculated_result(bad_match, rules)
    bad_report = evaluate_quality_control((bad_match,), (bad_calculation,), rules)
    assert "EXCEL_ERROR" in _codes(bad_report)


def test_decimal_tolerance_zero_policy_units_and_trace_totals_are_checked_exactly() -> None:
    tolerance_rules = quality_rule_set(tolerance=Decimal("0.10"))
    on_boundary_match = calculated_match(cost=Decimal("11"), target_cost=Decimal("10"))
    on_boundary = calculated_result(on_boundary_match, tolerance_rules)
    assert (
        evaluate_quality_control((on_boundary_match,), (on_boundary,), tolerance_rules).decision
        is QualityDecision.ALLOW_WRITE
    )
    outside_match = calculated_match(cost=Decimal("11.01"), target_cost=Decimal("10"))
    outside = calculated_result(outside_match, tolerance_rules)
    assert "TOLERANCE_EXCEEDED" in _codes(
        evaluate_quality_control((outside_match,), (outside,), tolerance_rules)
    )
    zero_match = calculated_match(cost=Decimal("1"), target_cost=Decimal("0"))
    zero = calculated_result(zero_match, tolerance_rules)
    zero_report = evaluate_quality_control((zero_match,), (zero,), tolerance_rules)
    assert "TOLERANCE_EXCEEDED" in _codes(zero_report)

    unit_conflict = calculated_match(target_unit="kg")
    unit_result = calculated_result(unit_conflict, quality_rule_set())
    unit_report = evaluate_quality_control((unit_conflict,), (unit_result,), quality_rule_set())
    assert "UNIT_CONFLICT" in _codes(unit_report)

    broken_total = replace(on_boundary, cost=Decimal("99"))
    report = evaluate_quality_control((on_boundary_match,), (broken_total,), tolerance_rules)
    assert {"TOTAL_DISCREPANCY", "TRACE_MISMATCH"} & _codes(report)


def test_duplicate_source_use_cardinality_and_reverse_order_are_deterministic() -> None:
    rules = quality_rule_set()
    first_match = calculated_match(result_id="a", target_row_id="ta", source_row_id="shared")
    second_match = calculated_match(result_id="b", target_row_id="tb", source_row_id="shared")
    first, second = calculated_result(first_match, rules), calculated_result(second_match, rules)
    forward = evaluate_quality_control((first_match, second_match), (first, second), rules)
    reverse = evaluate_quality_control((second_match, first_match), (second, first), rules)
    assert "SOURCE_ROW_REUSED" in _codes(forward)
    assert forward.report_id == reverse.report_id
    assert forward.input_digest == reverse.input_digest
    forward_ids = tuple(issue.issue_id for issue in forward.issues)
    reverse_ids = tuple(issue.issue_id for issue in reverse.issues)
    assert forward_ids == reverse_ids

    missing = evaluate_quality_control((first_match, second_match), (first,), rules)
    assert missing.decision is QualityDecision.BLOCK_WRITE
    assert "CARDINALITY_MISMATCH" in _codes(missing)
