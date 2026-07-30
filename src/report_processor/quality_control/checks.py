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
                "DUPLICATE_IDENTITY",
                "blocking",
                "обнаружена дублирующаяся identity",
                evidence={"identity_kind": label, "duplicate": duplicate},
            )


def check_match(match: MatchResult, issues: list) -> None:
    target = match.target_row
    if match.status is MatchStatus.UNMATCHED:
        issue(issues, "UNMATCHED", "manual_review", "строка не сопоставлена", match=match)
    elif match.status is MatchStatus.AMBIGUOUS:
        issue(issues, "AMBIGUOUS", "manual_review", "строка неоднозначна", match=match)
    if not getattr(target, "writable", False):
        issue(
            issues,
            "TARGET_NOT_WRITABLE",
            "blocking",
            "target row недоступен для записи",
            match=match,
        )
    if not getattr(target, "work_name", None):
        issue(issues, "MISSING_WORK_NAME", "manual_review", "у target нет work name", match=match)
    candidate = match.selected_candidate
    if candidate is None:
        return
    if not getattr(candidate.source_row, "work_name", None):
        issue(issues, "MISSING_WORK_NAME", "manual_review", "у source нет work name", match=match)
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
            "IDENTITY_MISMATCH",
            "blocking",
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
        issue(issues, "MISSING_PROVENANCE", "blocking", "source provenance неполный", match=match)
    if not isinstance(target, Mapping) or any(not target.get(key) for key in target_required):
        issue(issues, "MISSING_PROVENANCE", "blocking", "target provenance неполный", match=match)
    elif target["target_row_id"] != match.target_row_id:
        issue(
            issues,
            "PROVENANCE_CONFLICT",
            "blocking",
            "target provenance конфликтует с match",
            match=match,
        )


def _check_units(match: MatchResult, candidate: object, issues: list) -> None:
    dictionaries = TypoDictionaries()
    source_unit = normalize_unit(getattr(candidate.source_row, "unit", None), dictionaries)
    target_unit = normalize_unit(getattr(match.target_row, "unit", None), dictionaries)
    if source_unit is None or target_unit is None:
        issue(issues, "MISSING_UNIT", "manual_review", "единица измерения отсутствует", match=match)
    elif source_unit != target_unit:
        issue(
            issues,
            "UNIT_CONFLICT",
            "manual_review",
            "нормализованные units различаются",
            match=match,
        )


def _check_status(match: MatchResult, calculation: CalculationResult, issues: list) -> None:
    if calculation.status is CalculationStatus.NO_VALUES:
        issue(
            issues,
            "NO_VALUES",
            "blocking",
            "calculation не содержит значений",
            match=match,
            calculation=calculation,
        )
    elif calculation.status is CalculationStatus.MANUAL_REVIEW:
        issue(
            issues,
            "AMBIGUOUS",
            "manual_review",
            "calculation требует ручной проверки",
            match=match,
            calculation=calculation,
        )
    elif calculation.status is CalculationStatus.NO_MATCH:
        issue(
            issues,
            "UNMATCHED",
            "manual_review",
            "calculation не имеет match",
            match=match,
            calculation=calculation,
        )
    if calculation.warnings:
        issue(
            issues,
            "UPSTREAM_WARNING",
            "warning",
            "upstream calculation содержит warning",
            match=match,
            calculation=calculation,
        )


def _check_trace(match: MatchResult, calculation: CalculationResult, issues: list) -> None:
    trace = calculation.trace
    if trace.match_result_id != match.result_id or trace.target_row_id != match.target_row_id:
        issue(
            issues,
            "TRACE_MISMATCH",
            "blocking",
            "trace identity не совпадает",
            match=match,
            calculation=calculation,
        )
    if trace.rule_set_hash == "" or trace.category_totals != calculation.category_totals:
        issue(
            issues,
            "TRACE_MISMATCH",
            "blocking",
            "trace totals не совпадают",
            match=match,
            calculation=calculation,
        )
    if trace.formula_tokens != _FORMULA_TOKENS:
        issue(
            issues,
            "FORMULA_MISMATCH",
            "blocking",
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
            "TOTAL_DISCREPANCY",
            "blocking",
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
                "FORMULA_WITHOUT_CACHE",
                "blocking",
                "formula cache отсутствует",
                match=match,
                calculation=calculation,
            )
        elif "EXCEL_ERROR" in status or "EXCEL_ERROR" in cache:
            issue(
                issues,
                "EXCEL_ERROR",
                "blocking",
                "Excel error в target",
                match=match,
                calculation=calculation,
            )
        elif "VALUE_READ_FAILED" in status or "VALUE_READ_FAILED" in cache:
            issue(
                issues,
                "VALUE_READ_FAILED",
                "blocking",
                "target value не прочитан",
                match=match,
                calculation=calculation,
            )
        elif "FORMULA" in status and "CACHED" not in cache:
            issue(
                issues,
                "UNTRUSTED_FORMULA_CACHE",
                "blocking",
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
            "MISSING_REQUIRED_VALUE",
            "blocking",
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
            "TOLERANCE_EXCEEDED",
            "manual_review",
            "cost tolerance превышен",
            match=match,
            calculation=calculation,
        )


def _check_contributions(match: MatchResult, calculation: CalculationResult, issues: list) -> None:
    for contribution in calculation.trace.contributions:
        if _negative(contribution.raw_quantity) or _negative(contribution.raw_cost):
            issue(
                issues,
                "NEGATIVE_VALUE",
                "warning",
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
                "SIGN_CONFLICT",
                "manual_review",
                "quantity и cost имеют разные знаки",
                match=match,
                calculation=calculation,
                source_row_ids=(contribution.source_row_id,),
            )
        if not contribution.source_provenance or not contribution.target_provenance:
            issue(
                issues,
                "MISSING_PROVENANCE",
                "blocking",
                "contribution provenance неполный",
                match=match,
                calculation=calculation,
                source_row_ids=(contribution.source_row_id,),
            )


def _negative(value: Decimal | None) -> bool:
    return value is not None and value < Decimal("0")
