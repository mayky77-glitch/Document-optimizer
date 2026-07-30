"""Immutable public models for the deterministic calculation contract."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType

from report_processor.normalization import NormalizedSourceRow
from report_processor.target_report import TargetReportRow

CALCULATION_CONTRACT_VERSION = "CalculationContract-13.0"
CALCULATION_ENGINE_VERSION = "CalculationEngine-13.0"


class CalculationStatus(StrEnum):
    CALCULATED = "calculated"
    CALCULATED_WITH_WARNINGS = "calculated_with_warnings"
    NO_VALUES = "no_values"
    MANUAL_REVIEW = "manual_review"
    NO_MATCH = "no_match"


class CalculationCategory(StrEnum):
    WORK = "work"
    MATERIAL = "material"
    SERVICE = "service"
    UNCLASSIFIED = "unclassified"


def _freeze_mapping(values: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(dict(sorted(values.items())))


def _decimal_or_none(value: Decimal | None, field_name: str) -> None:
    if value is None:
        return
    if not isinstance(value, Decimal):
        raise TypeError(f"{field_name} должен быть Decimal или None")
    if not value.is_finite():
        raise ValueError(f"{field_name} должен быть конечным Decimal")


def _positive_decimal(value: Decimal, field_name: str) -> None:
    _decimal_or_none(value, field_name)
    if value is None or value <= Decimal("0"):
        raise ValueError(f"{field_name} должен быть положительным Decimal")


@dataclass(frozen=True, slots=True)
class CalculationContribution:
    contribution_id: str
    candidate_id: str
    source_row_id: str
    source_row: NormalizedSourceRow
    category: CalculationCategory
    raw_quantity: Decimal | None
    raw_cost: Decimal | None
    included_quantity: Decimal | None
    included_cost: Decimal | None
    include_quantity: bool
    include_cost: bool
    rule_ids: tuple[str, ...]
    decisions: tuple[str, ...]
    warnings: tuple[str, ...]
    source_provenance: Mapping[str, object]
    target_provenance: Mapping[str, object]

    def __post_init__(self) -> None:
        _decimal_or_none(self.raw_quantity, "raw_quantity")
        _decimal_or_none(self.raw_cost, "raw_cost")
        _decimal_or_none(self.included_quantity, "included_quantity")
        _decimal_or_none(self.included_cost, "included_cost")
        if not isinstance(self.include_quantity, bool) or not isinstance(self.include_cost, bool):
            raise TypeError("include flags должны быть bool")
        object.__setattr__(self, "rule_ids", tuple(sorted(set(self.rule_ids))))
        object.__setattr__(self, "decisions", tuple(self.decisions))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "source_provenance", _freeze_mapping(self.source_provenance))
        object.__setattr__(self, "target_provenance", _freeze_mapping(self.target_provenance))


@dataclass(frozen=True, slots=True)
class CalculationCategoryTotal:
    category: CalculationCategory
    quantity: Decimal | None
    cost_before_coefficient: Decimal | None
    coefficient: Decimal
    cost: Decimal | None

    def __post_init__(self) -> None:
        _decimal_or_none(self.quantity, "quantity")
        _decimal_or_none(self.cost_before_coefficient, "cost_before_coefficient")
        _decimal_or_none(self.cost, "cost")
        _positive_decimal(self.coefficient, "coefficient")


@dataclass(frozen=True, slots=True)
class CalculationTrace:
    trace_id: str
    match_result_id: str
    target_row_id: str
    rule_set_hash: str
    formula_tokens: tuple[str, ...]
    coefficient: Decimal
    rounding_quantum: Decimal
    rounding_mode: str
    contributions: tuple[CalculationContribution, ...]
    category_totals: tuple[CalculationCategoryTotal, ...]
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        _positive_decimal(self.coefficient, "coefficient")
        _positive_decimal(self.rounding_quantum, "rounding_quantum")
        if self.rounding_mode != "ROUND_HALF_UP":
            raise ValueError("rounding_mode должен быть ROUND_HALF_UP")
        if not isinstance(self.contributions, tuple) or not isinstance(self.category_totals, tuple):
            raise TypeError("trace collections должны быть tuple")
        if any(not isinstance(item, CalculationContribution) for item in self.contributions):
            raise TypeError("contributions содержит недопустимый элемент")
        if any(not isinstance(item, CalculationCategoryTotal) for item in self.category_totals):
            raise TypeError("category_totals содержит недопустимый элемент")
        object.__setattr__(self, "formula_tokens", tuple(self.formula_tokens))
        object.__setattr__(self, "contributions", tuple(self.contributions))
        object.__setattr__(self, "category_totals", tuple(self.category_totals))
        object.__setattr__(self, "warnings", tuple(self.warnings))


@dataclass(frozen=True, slots=True)
class CalculationResult:
    calculation_id: str
    target_row_id: str
    match_result_id: str
    target_row: TargetReportRow
    status: CalculationStatus
    quantity: Decimal | None
    cost_before_coefficient: Decimal | None
    coefficient: Decimal
    cost: Decimal | None
    category_totals: tuple[CalculationCategoryTotal, ...]
    trace: CalculationTrace
    warnings: tuple[str, ...]
    explanation: tuple[str, ...]
    contract_version: str = field(init=False, default=CALCULATION_CONTRACT_VERSION)

    def __post_init__(self) -> None:
        _decimal_or_none(self.quantity, "quantity")
        _decimal_or_none(self.cost_before_coefficient, "cost_before_coefficient")
        _decimal_or_none(self.cost, "cost")
        _positive_decimal(self.coefficient, "coefficient")
        if not isinstance(self.category_totals, tuple):
            raise TypeError("category_totals должен быть tuple")
        if any(not isinstance(item, CalculationCategoryTotal) for item in self.category_totals):
            raise TypeError("category_totals содержит недопустимый элемент")
        if not isinstance(self.trace, CalculationTrace):
            raise TypeError("trace должен быть CalculationTrace")
        if (
            self.trace.target_row_id != self.target_row_id
            or self.trace.match_result_id != self.match_result_id
        ):
            raise ValueError("trace не соответствует result identity")
        if (
            self.trace.coefficient != self.coefficient
            or self.trace.category_totals != self.category_totals
        ):
            raise ValueError("trace не соответствует calculation totals")
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "explanation", tuple(self.explanation))
