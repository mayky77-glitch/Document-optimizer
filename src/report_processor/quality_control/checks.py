"""Independent validation rules for the pre-write quality gate."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from decimal import Decimal

from report_processor.business_rules import ValidatedRuleSet
from report_processor.calculation import CalculationResult, CalculationStatus
from report_processor.matching import MatchResult, MatchStatus
from report_processor.normalization.models import TypoDictionaries
from report_processor.normalization.normalizers import normalize_unit

from .models import QualityIssueCode, QualityIssueSeverity
from .serialization import finite_decimal, issue, sum_optional

_FORMULA_TOKENS = (
    "quantity=quantize(sum(included_period_quantity),rounding_quantum,ROUND_HALF_UP)",
    "cost_before_coefficient=sum(included_period_cost)",
    "cost=quantize(cost_before_coefficient*default_run_coefficient,rounding_quantum,ROUND_HALF_UP)",
)


def check_duplicates(
    matches: tuple[MatchResult, ...], calculations: tuple[CalculationResult, ...], issues: list
) -> None:
    for label, values in (
        ("match_result_id", (item.result_id for item in matches)),
        ("target_row_id", (item.target_row_id for item in matches)),
        ("calculation_id", (item.calculation_id for item in calculations)),
        ("calculation_match_result_id", (item.match_result_id for item in calculations)),
    ):
        for duplicate in sorted(value for value, count in Counter(values).items() if count > 1):
            issue(
                issues,
                QualityIssueCode.DUPLICATE_IDENTITY,
                QualityIssueSeverity.BLOCKING,
                "обнаружена дублирующаяся identity",
                evidence={"identity_kind": label, "duplicate": duplicate},
            )


def check_match(match: MatchResult, issues: list) -> None:
    target = match.target_row
    if match.status is MatchStatus.UNMATCHED:
        issue(
            issues,
            QualityIssueCode.UNMATCHED,
            QualityIssueSeverity.MANUAL_REVIEW,
            "строка не сопоставлена",
            match=match,
        )
    elif match.status is MatchStatus.AMBIGUOUS:
        issue(
            issues,
            QualityIssueCode.AMBIGUOUS,
            QualityIssueSeverity.MANUAL_REVIEW,
            "строка неоднозначна",
            match=match,
        )
    if match.status is MatchStatus.MATCHED and not getattr(target, "writable", False):
        issue(
            issues,
            QualityIssueCode.TARGET_NOT_WRITABLE,
            QualityIssueSeverity.BLOCKING,
            "target row недоступен для записи",
            match=match,
        )
    if not getattr(target, "work_name", None):
        issue(
            issues,
            QualityIssueCode.MISSING_WORK_NAME,
            QualityIssueSeverity.MANUAL_REVIEW,
            "у target нет work name",
            match=match,
        )
    candidates = match.effective_selected_candidates
    if not candidates:
        return
    for candidate in candidates:
        if not getattr(candidate.source_row, "work_name", None):
            issue(
                issues,
                QualityIssueCode.MISSING_WORK_NAME,
                QualityIssueSeverity.MANUAL_REVIEW,
                "у source нет work name",
                match=match,
                source_row_ids=(candidate.source_row_id,),
            )
        _check_provenance(match, candidate, issues)
        _check_units(match, candidate, issues)


def check_calculation(
    match: MatchResult, calculation: CalculationResult, rule_set: ValidatedRuleSet, issues: list
) -> None:
    if (
        calculation.target_row_id != match.target_row_id
        or calculation.target_row is not match.target_row
    ):
        issue(
            issues,
            QualityIssueCode.IDENTITY_MISMATCH,
            QualityIssueSeverity.BLOCKING,
            "calculation identity не совпадает с match",
            match=match,
            calculation=calculation,
        )
    _check_status(match, calculation, issues)
    _check_trace(match, calculation, issues)
    _check_totals(match, calculation, issues)
    _check_numeric_cells(match, calculation, issues)
    _check_tolerance(match, calculation, rule_set, issues)
    _check_contributions(match, calculation, issues)


def _check_provenance(match: MatchResult, candidate: object, issues: list) -> None:
    source = getattr(candidate, "source_provenance", {})
    target = getattr(candidate, "target_provenance", {})
    source_required = (
        "source_file_id",
        "source_filename",
        "source_sheet",
        "source_row",
        "source_row_id",
    )
    target_required = ("target_source_id", "sheet_name", "row_number", "target_row_id")
    if not isinstance(source, Mapping) or any(not source.get(key) for key in source_required):
        issue(
            issues,
            QualityIssueCode.MISSING_PROVENANCE,
            QualityIssueSeverity.BLOCKING,
            "source provenance неполный",
            match=match,
        )
    if not isinstance(target, Mapping) or any(not target.get(key) for key in target_required):
        issue(
            issues,
            QualityIssueCode.MISSING_PROVENANCE,
            QualityIssueSeverity.BLOCKING,
            "target provenance неполный",
            match=match,
        )
    elif target["target_row_id"] != match.target_row_id:
        issue(
            issues,
            QualityIssueCode.PROVENANCE_CONFLICT,
            QualityIssueSeverity.BLOCKING,
            "target provenance конфликтует с match",
            match=match,
        )


def _check_units(match: MatchResult, candidate: object, issues: list) -> None:
    dictionaries = TypoDictionaries()
    source_unit = normalize_unit(getattr(candidate.source_row, "unit", None), dictionaries)
    target_unit = normalize_unit(getattr(match.target_row, "unit", None), dictionaries)
    if source_unit is None or target_unit is None:
        issue(
            issues,
            QualityIssueCode.MISSING_UNIT,
            QualityIssueSeverity.MANUAL_REVIEW,
            "единица измерения отсутствует",
            match=match,
        )
    elif source_unit != target_unit:
        issue(
            issues,
            QualityIssueCode.UNIT_CONFLICT,
            QualityIssueSeverity.MANUAL_REVIEW,
            "нормализованные units различаются",
            match=match,
        )


def _check_status(match: MatchResult, calculation: CalculationResult, issues: list) -> None:
    if calculation.status is CalculationStatus.NO_VALUES:
        issue(
            issues,
            QualityIssueCode.NO_VALUES,
            QualityIssueSeverity.BLOCKING,
            "calculation не содержит значений",
            match=match,
            calculation=calculation,
        )
    elif calculation.status is CalculationStatus.MANUAL_REVIEW:
        issue(
            issues,
            QualityIssueCode.AMBIGUOUS,
            QualityIssueSeverity.MANUAL_REVIEW,
            "calculation требует ручной проверки",
            match=match,
            calculation=calculation,
        )
    elif calculation.status is CalculationStatus.NO_MATCH:
        issue(
            issues,
            QualityIssueCode.UNMATCHED,
            QualityIssueSeverity.MANUAL_REVIEW,
            "calculation не имеет match",
            match=match,
            calculation=calculation,
        )
    if calculation.warnings:
        issue(
            issues,
            QualityIssueCode.UPSTREAM_WARNING,
            QualityIssueSeverity.WARNING,
            "upstream calculation содержит warning",
            match=match,
            calculation=calculation,
        )


def _check_trace(match: MatchResult, calculation: CalculationResult, issues: list) -> None:
    trace = calculation.trace
    if trace.match_result_id != match.result_id or trace.target_row_id != match.target_row_id:
        issue(
            issues,
            QualityIssueCode.TRACE_MISMATCH,
            QualityIssueSeverity.BLOCKING,
            "trace identity не совпадает",
            match=match,
            calculation=calculation,
        )
    if trace.rule_set_hash == "" or trace.category_totals != calculation.category_totals:
        issue(
            issues,
            QualityIssueCode.TRACE_MISMATCH,
            QualityIssueSeverity.BLOCKING,
            "trace totals не совпадают",
            match=match,
            calculation=calculation,
        )
    if trace.formula_tokens != _FORMULA_TOKENS:
        issue(
            issues,
            QualityIssueCode.FORMULA_MISMATCH,
            QualityIssueSeverity.BLOCKING,
            "formula tokens не совпадают",
            match=match,
            calculation=calculation,
        )


def _check_totals(match: MatchResult, calculation: CalculationResult, issues: list) -> None:
    totals = calculation.category_totals
    actual = (
        sum_optional(item.quantity for item in totals),
        sum_optional(item.cost_before_coefficient for item in totals),
        sum_optional(item.cost for item in totals),
    )
    expected = (calculation.quantity, calculation.cost_before_coefficient, calculation.cost)
    if actual != expected or any(item.coefficient != calculation.coefficient for item in totals):
        issue(
            issues,
            QualityIssueCode.TOTAL_DISCREPANCY,
            QualityIssueSeverity.BLOCKING,
            "category totals не совпадают",
            match=match,
            calculation=calculation,
        )


def _check_numeric_cells(match: MatchResult, calculation: CalculationResult, issues: list) -> None:
    for cell in (match.target_row.selected_quantity, match.target_row.selected_cost):
        if cell is None:
            continue
        status, cache = str(cell.status).upper(), str(cell.cache_state).upper()
        if "FORMULA_WITHOUT_CACH" in status or "FORMULA_WITHOUT_CACH" in cache:
            issue(
                issues,
                QualityIssueCode.FORMULA_WITHOUT_CACHE,
                QualityIssueSeverity.BLOCKING,
                "formula cache отсутствует",
                match=match,
                calculation=calculation,
            )
        elif "EXCEL_ERROR" in status or "EXCEL_ERROR" in cache:
            issue(
                issues,
                QualityIssueCode.EXCEL_ERROR,
                QualityIssueSeverity.BLOCKING,
                "Excel error в target",
                match=match,
                calculation=calculation,
            )
        elif "VALUE_READ_FAILED" in status or "VALUE_READ_FAILED" in cache:
            issue(
                issues,
                QualityIssueCode.VALUE_READ_FAILED,
                QualityIssueSeverity.BLOCKING,
                "target value не прочитан",
                match=match,
                calculation=calculation,
            )
        elif "FORMULA" in status and "CACHED" not in cache:
            issue(
                issues,
                QualityIssueCode.UNTRUSTED_FORMULA_CACHE,
                QualityIssueSeverity.BLOCKING,
                "formula cache не подтверждён",
                match=match,
                calculation=calculation,
            )


def _check_tolerance(
    match: MatchResult, calculation: CalculationResult, rule_set: ValidatedRuleSet, issues: list
) -> None:
    selected = match.target_row.selected_cost
    if selected is None or selected.value is None:
        return
    selected_cost = finite_decimal(selected.value, "selected_cost")
    if calculation.cost is None:
        issue(
            issues,
            QualityIssueCode.MISSING_REQUIRED_VALUE,
            QualityIssueSeverity.BLOCKING,
            "calculated cost отсутствует",
            match=match,
            calculation=calculation,
        )
        return
    calculated = finite_decimal(calculation.cost, "calculated_cost")
    exceeds = (
        calculated != 0
        if selected_cost == 0
        else abs(calculated - selected_cost) / abs(selected_cost)
        > rule_set.defaults.cost_tolerance_ratio
    )
    if exceeds:
        issue(
            issues,
            QualityIssueCode.TOLERANCE_EXCEEDED,
            QualityIssueSeverity.MANUAL_REVIEW,
            "cost tolerance превышен",
            match=match,
            calculation=calculation,
        )


def _check_contributions(match: MatchResult, calculation: CalculationResult, issues: list) -> None:
    selected_ids = {item.candidate_id for item in match.effective_selected_candidates}
    contribution_ids = {item.candidate_id for item in calculation.trace.contributions}
    if (
        calculation.status
        in {
            CalculationStatus.CALCULATED,
            CalculationStatus.CALCULATED_WITH_WARNINGS,
            CalculationStatus.NO_VALUES,
        }
        and contribution_ids != selected_ids
    ):
        issue(
            issues,
            QualityIssueCode.CARDINALITY_MISMATCH,
            QualityIssueSeverity.BLOCKING,
            "contribution set не совпадает с effective selected candidates",
            match=match,
            calculation=calculation,
            evidence={
                "selected_candidate_count": len(selected_ids),
                "contribution_candidate_count": len(contribution_ids),
            },
        )
    for contribution in calculation.trace.contributions:
        if contribution.candidate_id not in selected_ids:
            issue(
                issues,
                QualityIssueCode.IDENTITY_MISMATCH,
                QualityIssueSeverity.BLOCKING,
                "contribution не связан с effective selected candidate",
                match=match,
                calculation=calculation,
                source_row_ids=(contribution.source_row_id,),
            )
        if _negative(contribution.raw_quantity) or _negative(contribution.raw_cost):
            issue(
                issues,
                QualityIssueCode.NEGATIVE_VALUE,
                QualityIssueSeverity.WARNING,
                "обнаружено отрицательное значение",
                match=match,
                calculation=calculation,
                source_row_ids=(contribution.source_row_id,),
            )
        if (
            contribution.raw_quantity
            and contribution.raw_cost
            and contribution.raw_quantity.is_signed() != contribution.raw_cost.is_signed()
        ):
            issue(
                issues,
                QualityIssueCode.SIGN_CONFLICT,
                QualityIssueSeverity.MANUAL_REVIEW,
                "quantity и cost имеют разные знаки",
                match=match,
                calculation=calculation,
                source_row_ids=(contribution.source_row_id,),
            )
        if not contribution.source_provenance or not contribution.target_provenance:
            issue(
                issues,
                QualityIssueCode.MISSING_PROVENANCE,
                QualityIssueSeverity.BLOCKING,
                "contribution provenance неполный",
                match=match,
                calculation=calculation,
                source_row_ids=(contribution.source_row_id,),
            )


def _negative(value: Decimal | None) -> bool:
    return value is not None and value < Decimal("0")
