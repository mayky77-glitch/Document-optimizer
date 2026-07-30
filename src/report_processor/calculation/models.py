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
    category_totals: tuple[CalculationCategoryTotal, ...] | None
    trace: CalculationTrace | None
    warnings: tuple[str, ...]
    explanation: tuple[str, ...]
    contract_version: str = field(init=False, default=CALCULATION_CONTRACT_VERSION)

    def __post_init__(self) -> None:
        if self.category_totals is not None:
            object.__setattr__(self, "category_totals", tuple(self.category_totals))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "explanation", tuple(self.explanation))
