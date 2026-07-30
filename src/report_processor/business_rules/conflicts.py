"""Deterministic static conflict checks for validated business-rule data."""

from __future__ import annotations

from collections import defaultdict

from .models import (
    BusinessRule,
    RuleConflict,
    RuleConflictKind,
    RuleConflictReport,
    RuleMatchKind,
)


def detect_rule_conflicts(rule_set: object) -> RuleConflictReport:
    rules = getattr(rule_set, "rules", ())
    conflicts: list[RuleConflict] = []
    by_id: dict[str, list[BusinessRule]] = defaultdict(list)
    for rule in rules:
        by_id[rule.rule_id].append(rule)
    for rule_id, items in sorted(by_id.items()):
        if len(items) > 1:
            conflicts.append(
                RuleConflict(
                    RuleConflictKind.DUPLICATE_RULE_ID,
                    tuple(item.rule_id for item in items),
                    f"Правило {rule_id} определено несколько раз",
                )
            )
    for index, left in enumerate(rules):
        for right in rules[index + 1 :]:
            if not (left.exclusive_owner and right.exclusive_owner):
                continue
            if not _scope_overlap(left, right):
                continue
            if _same_include_literal(left, right):
                conflicts.append(
                    RuleConflict(
                        RuleConflictKind.EXCLUSIVE_SCOPE_OVERLAP,
                        tuple(sorted((left.rule_id, right.rule_id))),
                        "Exclusive rules overlap on the same scoped source literal",
                    )
                )
    return RuleConflictReport(tuple(conflicts))


def _scope_overlap(left: BusinessRule, right: BusinessRule) -> bool:
    return _overlap(left.scope.object_scopes, right.scope.object_scopes) and _overlap(
        left.scope.stages, right.scope.stages
    )


def _overlap(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    return not left or not right or bool(set(left) & set(right))


def _same_include_literal(left: BusinessRule, right: BusinessRule) -> bool:
    left_literals = {
        clause.literal.casefold()
        for clause in left.clauses
        if clause.match_kind is RuleMatchKind.EXACT and clause.action.value == "include"
    }
    right_literals = {
        clause.literal.casefold()
        for clause in right.clauses
        if clause.match_kind is RuleMatchKind.EXACT and clause.action.value == "include"
    }
    return bool(left_literals & right_literals)
