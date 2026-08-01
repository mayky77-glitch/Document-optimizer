"""Pure Decimal calculations over accepted matching results."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from hashlib import sha256

from report_processor.business_rules import RuleAction, RuleMatchKind, ValidatedRuleSet
from report_processor.matching import MatchCandidate, MatchResult, MatchStatus
from report_processor.normalization.models import TypoDictionaries
from report_processor.normalization.normalizers import (
    normalize_code,
    normalize_name,
    normalize_unit,
)

from .exceptions import CalculationInputError
from .models import (
    CALCULATION_CONTRACT_VERSION,
    CalculationCategory,
    CalculationCategoryTotal,
    CalculationContribution,
    CalculationResult,
    CalculationStatus,
    CalculationTrace,
)

_CATEGORIES = tuple(CalculationCategory)
_CATEGORY_BY_CODE = {category.value: category for category in _CATEGORIES[:-1]}
_FORMULA_TOKENS = (
    "quantity=quantize(sum(included_period_quantity),rounding_quantum,ROUND_HALF_UP)",
    "cost_before_coefficient=sum(included_period_cost)",
    "cost=quantize(cost_before_coefficient*default_run_coefficient,rounding_quantum,ROUND_HALF_UP)",
)


@dataclass(frozen=True, slots=True)
class _RuleDecision:
    include_quantity: bool
    include_cost: bool
    manual_review: bool
    excluded: bool
    decisions: tuple[str, ...]


def calculate_matches(
    match_results: Iterable[MatchResult],
    rule_set: ValidatedRuleSet,
    candidate_inclusions: Mapping[str, tuple[bool, bool]] | None = None,
    *,
    inclusion_flags: Mapping[str, tuple[bool, bool]] | None = None,
) -> tuple[CalculationResult, ...]:
    """Calculate accepted matches only; never execute configuration or write state."""

    if not isinstance(rule_set, ValidatedRuleSet):
        raise CalculationInputError("INVALID_RULE_SET", "rule_set должен быть ValidatedRuleSet")
    coefficient, quantum = _numeric_defaults(rule_set)
    results = tuple(match_results)
    if any(not isinstance(result, MatchResult) for result in results):
        raise CalculationInputError("INVALID_MATCH_RESULT", "match_results содержит не MatchResult")
    _reject_duplicates(results)
    if candidate_inclusions is not None and inclusion_flags is not None:
        raise CalculationInputError("AMBIGUOUS_CANDIDATE_INCLUSIONS", "use one inclusion mapping")
    inclusions = _validated_inclusions(candidate_inclusions or inclusion_flags)
    effective_ids = {
        candidate.candidate_id
        for result in results
        for candidate in result.effective_selected_candidates
    }
    unknown_ids = sorted(set(inclusions) - effective_ids)
    if unknown_ids:
        raise CalculationInputError("UNKNOWN_CANDIDATE_INCLUSION", ",".join(unknown_ids))
    return tuple(
        _calculate_result(result, rule_set, coefficient, quantum, inclusions)
        for result in sorted(results, key=lambda item: item.target_row_id)
    )


def _numeric_defaults(rule_set: ValidatedRuleSet) -> tuple[Decimal, Decimal]:
    coefficient = _finite_decimal(
        rule_set.defaults.default_run_coefficient, "default_run_coefficient"
    )
    quantum = _finite_decimal(rule_set.defaults.rounding_quantum, "rounding_quantum")
    if quantum <= Decimal("0"):
        raise CalculationInputError(
            "INVALID_ROUNDING_QUANTUM", "rounding_quantum должен быть больше нуля"
        )
    if coefficient <= Decimal("0"):
        raise CalculationInputError(
            "INVALID_COEFFICIENT", "default_run_coefficient должен быть больше нуля"
        )
    if rule_set.defaults.rounding_mode != ROUND_HALF_UP:
        raise CalculationInputError("INVALID_ROUNDING_MODE", "поддерживается только ROUND_HALF_UP")
    if rule_set.defaults.unit_conversion_enabled:
        raise CalculationInputError("UNIT_CONVERSION_FORBIDDEN", "конвертация единиц запрещена")
    return coefficient, quantum


def _calculate_result(
    match: MatchResult,
    rule_set: ValidatedRuleSet,
    coefficient: Decimal,
    quantum: Decimal,
    inclusions: Mapping[str, tuple[bool, bool]],
) -> CalculationResult:
    if match.status is MatchStatus.AMBIGUOUS:
        return _empty_result(
            match,
            rule_set,
            coefficient,
            quantum,
            CalculationStatus.MANUAL_REVIEW,
            "MATCH_AMBIGUOUS",
        )
    if match.status is MatchStatus.UNMATCHED:
        return _empty_result(
            match, rule_set, coefficient, quantum, CalculationStatus.NO_MATCH, "MATCH_UNMATCHED"
        )
    candidates = match.effective_selected_candidates
    if match.status is not MatchStatus.MATCHED or not candidates:
        raise CalculationInputError("INVALID_MATCH_STATUS", match.result_id)
    if any(candidate.target_row_id != match.target_row_id for candidate in candidates):
        raise CalculationInputError("CANDIDATE_TARGET_MISMATCH", match.result_id)
    decisions = tuple(_rule_decision(candidate, match, rule_set) for candidate in candidates)
    blocked = next((item for item in decisions if item.manual_review or item.excluded), None)
    if blocked is not None:
        reason = "RULE_EXCLUDE" if blocked.excluded else "RULE_REVIEW"
        return _empty_result(
            match, rule_set, coefficient, quantum, CalculationStatus.MANUAL_REVIEW, reason
        )
    contributions = tuple(
        _contribution(candidate, match, rule_set, decision, inclusions.get(candidate.candidate_id))
        for candidate, decision in zip(candidates, decisions, strict=True)
    )
    totals = _category_totals(contributions, coefficient, quantum)
    quantity = _round_sum(tuple(item.included_quantity for item in contributions), quantum)
    raw_cost = _sum_optional(tuple(item.included_cost for item in contributions))
    cost = _round_cost(raw_cost, coefficient, quantum)
    warnings = tuple(sorted({warning for item in contributions for warning in item.warnings}))
    status = (
        CalculationStatus.CALCULATED_WITH_WARNINGS if warnings else CalculationStatus.CALCULATED
    )
    if quantity is None and raw_cost is None:
        status = CalculationStatus.NO_VALUES
    trace = _trace(match, rule_set, coefficient, quantum, contributions, totals, warnings)
    calculation_id = _hash(
        "calculation",
        CALCULATION_CONTRACT_VERSION,
        match.target_row_id,
        match.result_id,
        trace.trace_id,
        rule_set.content_hash,
    )
    return CalculationResult(
        calculation_id=calculation_id,
        target_row_id=match.target_row_id,
        match_result_id=match.result_id,
        target_row=match.target_row,
        status=status,
        quantity=quantity,
        cost_before_coefficient=raw_cost,
        coefficient=coefficient,
        cost=cost,
        category_totals=totals,
        trace=trace,
        warnings=warnings,
        explanation=("selected_candidates_calculated",),
    )


def _empty_result(
    match: MatchResult,
    rule_set: ValidatedRuleSet,
    coefficient: Decimal,
    quantum: Decimal,
    status: CalculationStatus,
    reason: str,
) -> CalculationResult:
    warnings = (reason,)
    trace = _trace(match, rule_set, coefficient, quantum, (), (), warnings)
    calculation_id = _hash(
        "calculation-empty",
        CALCULATION_CONTRACT_VERSION,
        match.target_row_id,
        match.result_id,
        trace.trace_id,
        rule_set.content_hash,
        status,
    )
    return CalculationResult(
        calculation_id=calculation_id,
        target_row_id=match.target_row_id,
        match_result_id=match.result_id,
        target_row=match.target_row,
        status=status,
        quantity=None,
        cost_before_coefficient=None,
        coefficient=coefficient,
        cost=None,
        category_totals=(),
        trace=trace,
        warnings=warnings,
        explanation=(reason.lower(),),
    )


def _rule_decision(
    candidate: MatchCandidate, match: MatchResult, rule_set: ValidatedRuleSet
) -> _RuleDecision:
    if not candidate.rule_ids:
        return _RuleDecision(True, True, False, False, ("DEFAULT_INCLUDE",))
    rules = {rule.rule_id: rule for rule in rule_set.rules}
    include_quantity = False
    include_cost = False
    manual_review = False
    excluded = False
    decisions: list[str] = []
    for rule_id in sorted(set(candidate.rule_ids)):
        rule = rules.get(rule_id)
        if rule is None or not rule.owner_approved or rule.status != "approved":
            raise CalculationInputError("UNRESOLVED_RULE_ID", rule_id)
        matches = tuple(
            clause
            for clause in rule.clauses
            if _scope_matches(rule.scope, candidate, match)
            and _clause_matches(clause, candidate.source_row)
        )
        if not matches:
            raise CalculationInputError("RULE_DRIFT", rule_id)
        for clause in matches:
            decisions.append(f"{rule_id}:{clause.action.value}")
            if clause.action is RuleAction.EXCLUDE:
                excluded = True
            elif clause.action is RuleAction.REVIEW:
                manual_review = True
            elif clause.action is RuleAction.INCLUDE:
                include_quantity = include_quantity or clause.include_quantity
                include_cost = include_cost or clause.include_cost
    return _RuleDecision(
        include_quantity, include_cost, manual_review, excluded, tuple(sorted(set(decisions)))
    )


def _scope_matches(scope, candidate: MatchCandidate, match: MatchResult) -> bool:
    dictionaries = TypoDictionaries()
    return (
        _in_scope(match.target_row.object_code, scope.object_scopes, normalize_code, dictionaries)
        and _in_scope(match.target_row.stage, scope.stages, normalize_name, dictionaries)
        and _in_scope(
            match.target_row.work_name, scope.target_processes, normalize_name, dictionaries
        )
        and _in_scope(candidate.source_row.unit, scope.source_units, normalize_unit, dictionaries)
    )


def _in_scope(value, allowed, normalizer, dictionaries: TypoDictionaries) -> bool:
    if not allowed:
        return True
    normalized = tuple(item for raw in allowed if (item := normalizer(raw, dictionaries)))
    return value is not None and normalizer(value, dictionaries) in normalized


def _clause_matches(clause, source) -> bool:
    name = source.work_name
    if name is None:
        return False
    dictionaries = TypoDictionaries()
    literal = normalize_name(clause.literal, dictionaries)
    if literal is None:
        return False
    if clause.match_kind is RuleMatchKind.EXACT:
        name_matches = name == literal
    elif clause.match_kind is RuleMatchKind.PREFIX:
        name_matches = name.startswith(literal)
    else:
        name_matches = literal in name
    source_unit = normalize_unit(source.unit, dictionaries)
    allowed_units = tuple(
        item for raw in clause.source_units if (item := normalize_unit(raw, dictionaries))
    )
    excluded_units = tuple(
        item for raw in clause.excluded_units if (item := normalize_unit(raw, dictionaries))
    )
    required = tuple(
        item for raw in clause.required_substrings if (item := normalize_name(raw, dictionaries))
    )
    forbidden = tuple(
        item for raw in clause.forbidden_substrings if (item := normalize_name(raw, dictionaries))
    )
    return (
        name_matches
        and (not allowed_units or source_unit in allowed_units)
        and source_unit not in excluded_units
        and all(token in name for token in required)
        and not any(token in name for token in forbidden)
    )


def _contribution(
    candidate: MatchCandidate,
    match: MatchResult,
    rule_set: ValidatedRuleSet,
    decision: _RuleDecision,
    inclusion: tuple[bool, bool] | None,
) -> CalculationContribution:
    source = candidate.source_row
    raw_quantity = _optional_decimal(source.source_row.period_quantity, "period_quantity")
    raw_cost = _optional_decimal(source.source_row.period_cost, "period_cost")
    include_quantity, include_cost = inclusion or (decision.include_quantity, decision.include_cost)
    quantity_allowed = include_quantity and _quantity_unit_allowed(
        source.unit, match.target_row.unit, rule_set
    )
    warnings: list[str] = []
    if include_quantity and not quantity_allowed:
        warnings.append("QUANTITY_UNIT_MISMATCH")
    included_quantity = raw_quantity if quantity_allowed else None
    included_cost = raw_cost if include_cost else None
    for value, label in ((raw_quantity, "QUANTITY"), (raw_cost, "COST")):
        if value is not None and value < 0:
            warnings.append(f"NEGATIVE_{label}")
    category = _CATEGORY_BY_CODE.get(source.cost_type_code, CalculationCategory.UNCLASSIFIED)
    contribution_id = _hash(
        "contribution",
        CALCULATION_CONTRACT_VERSION,
        match.result_id,
        candidate.candidate_id,
        rule_set.content_hash,
        source.source_row_id,
        raw_quantity,
        raw_cost,
        included_quantity,
        included_cost,
        decision.decisions,
    )
    return CalculationContribution(
        contribution_id=contribution_id,
        candidate_id=candidate.candidate_id,
        source_row_id=source.source_row_id,
        source_row=source,
        category=category,
        raw_quantity=raw_quantity,
        raw_cost=raw_cost,
        included_quantity=included_quantity,
        included_cost=included_cost,
        include_quantity=quantity_allowed,
        include_cost=include_cost,
        rule_ids=candidate.rule_ids,
        decisions=decision.decisions,
        warnings=tuple(sorted(set(warnings))),
        source_provenance=dict(candidate.source_provenance),
        target_provenance=dict(candidate.target_provenance),
    )


def _quantity_unit_allowed(
    source_unit: str | None, target_unit: str | None, rule_set: ValidatedRuleSet
) -> bool:
    dictionaries = TypoDictionaries()
    source_normalized = normalize_unit(source_unit, dictionaries)
    target_normalized = normalize_unit(target_unit, dictionaries)
    allowed = tuple(
        item
        for raw in rule_set.defaults.allowed_units
        if (item := normalize_unit(raw, dictionaries)) is not None
    )
    if allowed and source_normalized not in allowed:
        return False
    return target_normalized is None or source_normalized == target_normalized


def _category_totals(
    contributions: tuple[CalculationContribution, ...], coefficient: Decimal, quantum: Decimal
) -> tuple[CalculationCategoryTotal, ...]:
    by_category: dict[CalculationCategory, list[CalculationContribution]] = defaultdict(list)
    for contribution in contributions:
        by_category[contribution.category].append(contribution)
    return tuple(
        CalculationCategoryTotal(
            category=category,
            quantity=_round_sum(
                tuple(item.included_quantity for item in by_category.get(category, [])), quantum
            ),
            cost_before_coefficient=_sum_optional(
                tuple(item.included_cost for item in by_category.get(category, []))
            ),
            coefficient=coefficient,
            cost=_round_cost(
                _sum_optional(tuple(item.included_cost for item in by_category.get(category, []))),
                coefficient,
                quantum,
            ),
        )
        for category in _CATEGORIES
    )


def _trace(
    match: MatchResult,
    rule_set: ValidatedRuleSet,
    coefficient: Decimal,
    quantum: Decimal,
    contributions: tuple[CalculationContribution, ...],
    totals: tuple[CalculationCategoryTotal, ...],
    warnings: tuple[str, ...],
) -> CalculationTrace:
    ordered = tuple(sorted(contributions, key=lambda item: (item.source_row_id, item.candidate_id)))
    trace_id = _hash(
        "trace",
        CALCULATION_CONTRACT_VERSION,
        match.result_id,
        match.target_row_id,
        rule_set.content_hash,
        coefficient,
        quantum,
        ROUND_HALF_UP,
        tuple(item.contribution_id for item in ordered),
        totals,
    )
    return CalculationTrace(
        trace_id=trace_id,
        match_result_id=match.result_id,
        target_row_id=match.target_row_id,
        rule_set_hash=rule_set.content_hash,
        formula_tokens=_FORMULA_TOKENS,
        coefficient=coefficient,
        rounding_quantum=quantum,
        rounding_mode=ROUND_HALF_UP,
        contributions=ordered,
        category_totals=totals,
        warnings=warnings,
    )


def _round_sum(values: tuple[Decimal | None, ...], quantum: Decimal) -> Decimal | None:
    value = _sum_optional(values)
    return None if value is None else _round_to_quantum(value, quantum)


def _round_cost(value: Decimal | None, coefficient: Decimal, quantum: Decimal) -> Decimal | None:
    return None if value is None else _round_to_quantum(value * coefficient, quantum)


def _round_to_quantum(value: Decimal, quantum: Decimal) -> Decimal:
    """Round to a quantum multiple, not merely to its decimal exponent."""

    try:
        required_precision = max(
            64,
            len(value.as_tuple().digits)
            + len(quantum.as_tuple().digits)
            + abs(value.adjusted())
            + abs(quantum.adjusted())
            + 12,
        )
        with localcontext() as context:
            context.prec = required_precision
            multiples = (value / quantum).to_integral_value(rounding=ROUND_HALF_UP)
            return multiples * quantum
    except (InvalidOperation, ValueError) as error:
        raise CalculationInputError("ROUNDING_ERROR", str(error)) from error


def _sum_optional(values: tuple[Decimal | None, ...]) -> Decimal | None:
    present = tuple(value for value in values if value is not None)
    return sum(present, Decimal("0")) if present else None


def _optional_decimal(value: object, field: str) -> Decimal | None:
    return None if value is None else _finite_decimal(value, field)


def _finite_decimal(value: object, field: str) -> Decimal:
    if isinstance(value, float) or not isinstance(value, Decimal) or not value.is_finite():
        raise CalculationInputError("INVALID_DECIMAL", field)
    return value


def _reject_duplicates(results: tuple[MatchResult, ...]) -> None:
    for field in ("result_id", "target_row_id"):
        values = [getattr(result, field) for result in results]
        if len(values) != len(set(values)):
            raise CalculationInputError("DUPLICATE_MATCH_IDENTITY", field)


def _validated_inclusions(
    values: Mapping[str, tuple[bool, bool]] | None,
) -> Mapping[str, tuple[bool, bool]]:
    if values is None:
        return {}
    if not isinstance(values, Mapping):
        raise CalculationInputError("INVALID_CANDIDATE_INCLUSIONS", "candidate_inclusions")
    normalized: dict[str, tuple[bool, bool]] = {}
    for candidate_id, flags in values.items():
        if (
            not isinstance(candidate_id, str)
            or not candidate_id
            or not isinstance(flags, tuple)
            or len(flags) != 2
            or any(not isinstance(flag, bool) for flag in flags)
        ):
            raise CalculationInputError("INVALID_CANDIDATE_INCLUSIONS", str(candidate_id))
        normalized[candidate_id] = flags
    return normalized


def _hash(*parts: object) -> str:
    try:
        payload = json.dumps(parts, ensure_ascii=False, separators=(",", ":"), default=str)
    except (TypeError, ValueError, InvalidOperation) as error:
        raise CalculationInputError("IDENTITY_SERIALIZATION_ERROR", str(error)) from error
    return sha256(payload.encode("utf-8")).hexdigest()
