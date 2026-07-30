"""Immutable models for the versioned, data-only business-rules contract."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class RuleAction(StrEnum):
    INCLUDE = "include"
    EXCLUDE = "exclude"
    REVIEW = "needs_review"


class RuleMatchKind(StrEnum):
    EXACT = "exact"
    PREFIX = "prefix"
    CONTAINS = "contains"


class RulePrecedence(StrEnum):
    HARD_EXCLUDE = "hard_exclude"
    EXCLUSIVE_OWNERSHIP = "exclusive_ownership"
    APPROVED_SCOPED_EXACT = "approved_scoped_exact"
    APPROVED_FEEDBACK = "approved_feedback"
    BASELINE_CANDIDATE = "baseline_candidate"
    MANUAL_REVIEW = "manual_review"


class QuantityPolicy(StrEnum):
    TARGET_UNIT_OR_SINGLE_ALTERNATIVE = "target_unit_or_single_alternative"


class CostPolicy(StrEnum):
    ALL_APPROVED_ROWS = "all_approved_rows"


class RuleSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class RuleConflictKind(StrEnum):
    DUPLICATE_RULE_ID = "duplicate_rule_id"
    EXCLUSIVE_SCOPE_OVERLAP = "exclusive_scope_overlap"
    PRECEDENCE_TIE = "precedence_tie"


@dataclass(frozen=True, slots=True)
class RuleConfigurationVersion:
    value: str = "RuleConfigurationVersion-1.0"


@dataclass(frozen=True, slots=True)
class RuleScope:
    object_scopes: tuple[str, ...] = ()
    stages: tuple[str, ...] = ()
    target_processes: tuple[str, ...] = ()
    source_units: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RuleClause:
    action: RuleAction
    match_kind: RuleMatchKind
    literal: str
    field: str = "source_work_name"
    priority: int = 0
    hard_exclude: bool = False
    required_substrings: tuple[str, ...] = ()
    forbidden_substrings: tuple[str, ...] = ()
    source_units: tuple[str, ...] = ()
    excluded_units: tuple[str, ...] = ()
    include_quantity: bool = True
    include_cost: bool = True

    @property
    def decision(self) -> RuleAction:
        return self.action

    @property
    def match_mode(self) -> RuleMatchKind:
        return self.match_kind


@dataclass(frozen=True, slots=True)
class BusinessRule:
    rule_id: str
    rule_version: str
    scope: RuleScope
    clauses: tuple[RuleClause, ...]
    priority: int
    exclusive_owner: bool = False
    owner_approved: bool = True
    evidence: tuple[str, ...] = ()
    status: str = "approved"
    subject: str = "source_work_name"
    origin: str = "baseline"


@dataclass(frozen=True, slots=True)
class RuleDefaults:
    source_priority: tuple[str, ...]
    allowed_units: tuple[str, ...]
    default_run_coefficient: Decimal
    rounding_quantum: Decimal
    rounding_mode: str
    cost_tolerance_ratio: Decimal
    quantity_policy: QuantityPolicy
    cost_policy: CostPolicy
    unit_conversion_enabled: bool = False

    @property
    def coefficient(self) -> Decimal:
        return self.default_run_coefficient

    @property
    def tolerance(self) -> Decimal:
        return self.cost_tolerance_ratio

    @property
    def quantum(self) -> Decimal:
        return self.rounding_quantum

    @property
    def rounding(self) -> str:
        return self.rounding_mode


@dataclass(frozen=True, slots=True)
class ValidatedRuleSet:
    configuration_version: RuleConfigurationVersion
    rule_set_version: str
    defaults: RuleDefaults
    rules: tuple[BusinessRule, ...]
    canonical_json: bytes
    content_hash: str


@dataclass(frozen=True, slots=True)
class RuleConflict:
    kind: RuleConflictKind
    rule_ids: tuple[str, ...]
    message: str


@dataclass(frozen=True, slots=True)
class RuleConflictReport:
    conflicts: tuple[RuleConflict, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.conflicts


@dataclass(frozen=True, slots=True)
class RuleValidationIssue:
    code: str
    message: str
    path: str = "$"
    severity: RuleSeverity = RuleSeverity.ERROR


@dataclass(frozen=True, slots=True)
class RuleValidationResult:
    rule_set: ValidatedRuleSet | None
    issues: tuple[RuleValidationIssue, ...] = ()
    conflicts: RuleConflictReport = RuleConflictReport()

    @property
    def valid(self) -> bool:
        return (
            self.rule_set is not None
            and not any(issue.severity is RuleSeverity.ERROR for issue in self.issues)
            and self.conflicts.valid
        )
