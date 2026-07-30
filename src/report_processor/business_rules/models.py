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


@dataclass(frozen=True, slots=True)
class RuleDefaults:
    coefficient: Decimal
    tolerance: Decimal
    quantum: Decimal
    rounding: str
    unit_conversion_enabled: bool
    source_priority: tuple[str, ...]


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
