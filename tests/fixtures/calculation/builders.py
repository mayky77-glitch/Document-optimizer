"""Small immutable fixtures for Decimal-only calculation behaviour."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from fixtures.matching.builders import rule_set as base_rule_set
from fixtures.matching.builders import source_row as base_source_row
from fixtures.matching.builders import target_row
from report_processor.business_rules.models import (
    BusinessRule,
    RuleAction,
    RuleClause,
    RuleDefaults,
    RuleMatchKind,
    RuleScope,
)
from report_processor.matching import MatchCandidate, MatchResult, MatchStatus, MatchStrategy


def calculation_source_row(
    source_row_id: str = "source-a:17",
    *,
    quantity: Decimal | None = Decimal("2.50"),
    cost: Decimal | None = Decimal("25.00"),
    unit: str | None = "m",
    cost_type_code: str | None = "SMR",
    work_name: str = "pipe installation",
) -> object:
    """Build a normalized source whose original Decimal values remain visible."""

    normalized = base_source_row(source_row_id, unit=unit, work_name=work_name)
    original = replace(
        normalized.source_row,
        period_quantity=quantity,
        period_cost=cost,
        cost_type_code=cost_type_code,
    )
    key = replace(normalized.business_key, cost_type_code=cost_type_code, unit=unit)
    return replace(
        normalized,
        source_row=original,
        business_key=key,
        cost_type_code=cost_type_code,
        unit=unit,
    )


def calculation_rule_set(
    *,
    coefficient: Decimal = Decimal("1.0"),
    quantum: Decimal = Decimal("0.01"),
    allowed_units: tuple[str, ...] = ("m",),
    action: RuleAction = RuleAction.INCLUDE,
    include_quantity: bool = True,
    include_cost: bool = True,
    owner_approved: bool = True,
    status: str = "approved",
    source_priority: tuple[str, ...] = ("ks6a",),
) -> object:
    """Build one data-only rule set with independently controllable decisions."""

    baseline = base_rule_set()
    defaults = RuleDefaults(
        source_priority=source_priority,
        allowed_units=allowed_units,
        default_run_coefficient=coefficient,
        rounding_quantum=quantum,
        rounding_mode="ROUND_HALF_UP",
        cost_tolerance_ratio=Decimal("0"),
        quantity_policy=baseline.defaults.quantity_policy,
        cost_policy=baseline.defaults.cost_policy,
    )
    rule = BusinessRule(
        rule_id="C13",
        rule_version="1",
        scope=RuleScope(),
        clauses=(
            RuleClause(
                action=action,
                match_kind=RuleMatchKind.EXACT,
                literal="pipe installation",
                include_quantity=include_quantity,
                include_cost=include_cost,
            ),
        ),
        priority=10,
        owner_approved=owner_approved,
        status=status,
        evidence=("synthetic",),
    )
    return replace(baseline, defaults=defaults, rules=(rule,))


def match_result(
    source: object,
    *,
    result_id: str = "match-result-a",
    status: MatchStatus = MatchStatus.MATCHED,
    candidate_id: str = "candidate-a",
    target_row_id: str = "target-a",
    row_number: int = 8,
    target_unit: str | None = "m",
) -> MatchResult:
    """Build a selected or non-selected immutable matching result."""

    target = target_row(row_number=row_number, unit=target_unit)
    candidate = MatchCandidate(
        candidate_id=candidate_id,
        target_row_id=target_row_id,
        source_row_id=source.source_row_id,
        source_row=source,
        strategies=(MatchStrategy.EXACT_BUSINESS_KEY,),
        confidence=Decimal("1"),
        rule_ids=("C13",),
        explanation=("fixture",),
        source_provenance=dict(source.provenance),
        target_provenance={
            "target_source_id": "target",
            "sheet_name": "Table 2",
            "row_number": row_number,
            "target_row_id": target_row_id,
        },
    )
    selected = candidate if status is MatchStatus.MATCHED else None
    return MatchResult(
        result_id=result_id,
        target_row_id=target_row_id,
        target_row=target,
        status=status,
        selected_candidate=selected,
        candidates=(candidate,),
        warnings=(),
        explanation=("fixture",),
    )
