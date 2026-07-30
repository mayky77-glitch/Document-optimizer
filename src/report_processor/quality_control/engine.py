"""Public deterministic quality-gate entry point."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal

from report_processor.business_rules import ValidatedRuleSet
from report_processor.calculation import CalculationResult
from report_processor.matching import MatchResult

from .checks import check_calculation, check_duplicates, check_match
from .exceptions import QualityControlInputError
from .models import QualityControlReport
from .serialization import (
    decision,
    digest,
    finite_decimal,
    issue,
    issue_sort_key,
    report_identity,
    summary,
)


def evaluate_quality_control(
    match_results: Iterable[MatchResult],
    calculation_results: Iterable[CalculationResult],
    rule_set: ValidatedRuleSet,
) -> QualityControlReport:
    """Evaluate matching and calculation artifacts without writing or exposing cell content."""

    matches = tuple(match_results)
    calculations = tuple(calculation_results)
    _validate_inputs(matches, calculations, rule_set)
    issues = []
    check_duplicates(matches, calculations, issues)
    by_match: defaultdict[str, list[CalculationResult]] = defaultdict(list)
    for calculation in calculations:
        by_match[calculation.match_result_id].append(calculation)
    match_ids = {match.result_id for match in matches}
    for match in sorted(matches, key=lambda item: (item.target_row_id, item.result_id)):
        linked = tuple(by_match[match.result_id])
        if len(linked) != 1:
            issue(
                issues,
                "CARDINALITY_MISMATCH",
                "blocking",
                "для match result нужен ровно один calculation result",
                match=match,
                evidence={"calculation_count": len(linked)},
            )
        check_match(match, issues)
        if len(linked) == 1:
            check_calculation(match, linked[0], rule_set, issues)
    for calculation in sorted(calculations, key=lambda item: item.calculation_id):
        if calculation.match_result_id not in match_ids:
            issue(
                issues,
                "CARDINALITY_MISMATCH",
                "blocking",
                "calculation не связан с match result",
                calculation=calculation,
            )
    _check_source_reuse(matches, issues)
    ordered = tuple(sorted(issues, key=issue_sort_key))
    input_digest = digest(matches, calculations, rule_set)
    result_decision = decision(ordered)
    return QualityControlReport(
        report_id=report_identity(
            input_digest,
            result_decision,
            tuple(item.issue_id for item in ordered),
        ),
        input_digest=input_digest,
        rule_set_hash=rule_set.content_hash,
        decision=result_decision,
        issues=ordered,
        summary=summary(matches, calculations, ordered),
        match_result_ids=tuple(item.result_id for item in matches),
        calculation_ids=tuple(item.calculation_id for item in calculations),
    )


def _validate_inputs(
    matches: tuple[MatchResult, ...],
    calculations: tuple[CalculationResult, ...],
    rule_set: ValidatedRuleSet,
) -> None:
    if not isinstance(rule_set, ValidatedRuleSet):
        raise QualityControlInputError("INVALID_RULE_SET", "rule_set должен быть ValidatedRuleSet")
    if any(not isinstance(item, MatchResult) for item in matches):
        raise QualityControlInputError(
            "INVALID_MATCH_RESULT", "match_results содержит не MatchResult"
        )
    if any(not isinstance(item, CalculationResult) for item in calculations):
        raise QualityControlInputError(
            "INVALID_CALCULATION_RESULT", "calculation_results содержит не CalculationResult"
        )
    tolerance = finite_decimal(rule_set.defaults.cost_tolerance_ratio, "cost_tolerance_ratio")
    if tolerance < Decimal("0"):
        raise QualityControlInputError("INVALID_TOLERANCE", "cost_tolerance_ratio должен быть >= 0")


def _check_source_reuse(matches: tuple[MatchResult, ...], issues: list) -> None:
    used: defaultdict[str, list[MatchResult]] = defaultdict(list)
    for match in matches:
        if match.selected_candidate is not None:
            used[match.selected_candidate.source_row_id].append(match)
    for source_row_id, linked in sorted(used.items()):
        if len(linked) > 1:
            for match in linked:
                issue(
                    issues,
                    "SOURCE_ROW_REUSED",
                    "manual_review",
                    "source row выбран более одного раза",
                    match=match,
                    source_row_ids=(source_row_id,),
                )
