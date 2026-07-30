"""Strict validation and canonicalization for a non-executable rule-set payload."""

from __future__ import annotations

import hashlib
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .conflicts import detect_rule_conflicts
from .defaults import default_payload
from .models import (
    BusinessRule,
    RuleAction,
    RuleClause,
    RuleConfigurationVersion,
    RuleDefaults,
    RuleMatchKind,
    RuleScope,
    RuleValidationIssue,
    RuleValidationResult,
    ValidatedRuleSet,
)
from .parsing import (
    ConfigurationParseError,
    canonical_json_bytes,
    check_depth,
    load_configuration_payload,
)

_ROOT_KEYS = frozenset({"configuration_version", "rule_set_version", "defaults", "rules"})
_DEFAULT_KEYS = frozenset(
    {
        "coefficient",
        "tolerance",
        "quantum",
        "rounding",
        "unit_conversion_enabled",
        "source_priority",
    }
)
_RULE_KEYS = frozenset(
    {
        "rule_id",
        "rule_version",
        "scope",
        "clauses",
        "priority",
        "exclusive_owner",
        "owner_approved",
        "evidence",
    }
)
_SCOPE_KEYS = frozenset({"object_scopes", "stages", "target_processes", "source_units"})
_CLAUSE_KEYS = frozenset({"action", "match_kind", "literal", "field", "priority", "hard_exclude"})
_FORBIDDEN_TEXT = (
    "${",
    "{{",
    "}}",
    "env:",
    "include",
    "file:",
    "http://",
    "https://",
    "shell",
    "eval",
    "exec",
    "import",
    "callable",
    "regex",
)
_SOURCE_PRIORITY = (
    "hard_exclude",
    "exclusive_ownership",
    "approved_scoped_exact",
    "approved_feedback",
    "baseline_candidate",
    "manual_review",
)


def validate_rule_payload(payload: object) -> RuleValidationResult:
    issues: list[RuleValidationIssue] = []
    try:
        check_depth(payload)
    except ConfigurationParseError as error:
        return _invalid("INVALID_STRUCTURE", str(error))
    if not isinstance(payload, dict):
        return _invalid("ROOT_TYPE", "Корень конфигурации должен быть объектом")
    _unknown_keys(payload, _ROOT_KEYS, "$", issues)
    if issues:
        return _result(None, issues)
    if payload.get("configuration_version") != "RuleConfigurationVersion-1.0":
        issues.append(
            _issue(
                "CONFIGURATION_VERSION",
                "Неподдерживаемая configuration_version",
                "$.configuration_version",
            )
        )
    if payload.get("rule_set_version") != "ValidatedRuleSet-10.0":
        issues.append(
            _issue("RULE_SET_VERSION", "Неподдерживаемая rule_set_version", "$.rule_set_version")
        )
    defaults = _parse_defaults(payload.get("defaults"), issues)
    rules = _parse_rules(payload.get("rules"), issues)
    if issues or defaults is None or rules is None:
        return _result(None, issues)
    canonical_payload = _canonical_payload(defaults, rules)
    canonical_json = canonical_json_bytes(canonical_payload)
    rule_set = ValidatedRuleSet(
        RuleConfigurationVersion(),
        "ValidatedRuleSet-10.0",
        defaults,
        tuple(sorted(rules, key=lambda rule: rule.rule_id)),
        canonical_json,
        hashlib.sha256(canonical_json).hexdigest(),
    )
    conflicts = detect_rule_conflicts(rule_set)
    return RuleValidationResult(rule_set if conflicts.valid else None, (), conflicts)


def load_rule_configuration(path: Path) -> RuleValidationResult:
    try:
        return validate_rule_payload(load_configuration_payload(path))
    except ConfigurationParseError as error:
        return _invalid("PARSE_ERROR", str(error))


def load_default_rule_set() -> RuleValidationResult:
    return validate_rule_payload(default_payload())


def _parse_defaults(value: object, issues: list[RuleValidationIssue]) -> RuleDefaults | None:
    path = "$.defaults"
    if not isinstance(value, dict):
        issues.append(_issue("DEFAULTS_TYPE", "defaults должен быть объектом", path))
        return None
    _unknown_keys(value, _DEFAULT_KEYS, path, issues)
    coefficient = _decimal(value.get("coefficient"), f"{path}.coefficient", issues, positive=True)
    tolerance = _decimal(value.get("tolerance"), f"{path}.tolerance", issues, positive=False)
    quantum = _decimal(value.get("quantum"), f"{path}.quantum", issues, positive=True)
    rounding = value.get("rounding")
    if rounding != "ROUND_HALF_UP":
        issues.append(_issue("ROUNDING", "Поддерживается только ROUND_HALF_UP", f"{path}.rounding"))
    conversion = value.get("unit_conversion_enabled")
    if conversion is not False:
        issues.append(
            _issue(
                "UNIT_CONVERSION",
                "Конвертация единиц по умолчанию отключена",
                f"{path}.unit_conversion_enabled",
            )
        )
    source_priority = value.get("source_priority")
    if source_priority != list(_SOURCE_PRIORITY):
        issues.append(
            _issue(
                "SOURCE_PRIORITY",
                "Источник приоритета должен быть фиксированным",
                f"{path}.source_priority",
            )
        )
    if issues or coefficient is None or tolerance is None or quantum is None:
        return None
    if coefficient > Decimal("100") or tolerance > Decimal("1") or quantum > Decimal("1"):
        issues.append(_issue("DEFAULT_RANGE", "Недопустимый диапазон default Decimal", path))
        return None
    return RuleDefaults(coefficient, tolerance, quantum, str(rounding), False, _SOURCE_PRIORITY)


def _parse_rules(value: object, issues: list[RuleValidationIssue]) -> list[BusinessRule] | None:
    if not isinstance(value, list) or not value:
        issues.append(_issue("RULES_TYPE", "rules должен быть непустым массивом", "$.rules"))
        return None
    if len(value) > 1000:
        issues.append(_issue("RULE_LIMIT", "Лимит rules: 1000", "$.rules"))
        return None
    parsed: list[BusinessRule] = []
    for index, item in enumerate(value):
        rule = _parse_rule(item, index, issues)
        if rule is not None:
            parsed.append(rule)
    return parsed if not issues else None


def _parse_rule(
    value: object, index: int, issues: list[RuleValidationIssue]
) -> BusinessRule | None:
    path = f"$.rules[{index}]"
    if not isinstance(value, dict):
        issues.append(_issue("RULE_TYPE", "rule должен быть объектом", path))
        return None
    _unknown_keys(value, _RULE_KEYS, path, issues)
    rule_id = _string(value.get("rule_id"), f"{path}.rule_id", issues)
    rule_version = _string(value.get("rule_version"), f"{path}.rule_version", issues)
    priority = _integer(value.get("priority"), f"{path}.priority", issues)
    scope = _parse_scope(value.get("scope"), f"{path}.scope", issues)
    clauses = _parse_clauses(value.get("clauses"), f"{path}.clauses", issues)
    exclusive = _boolean(value.get("exclusive_owner", False), f"{path}.exclusive_owner", issues)
    approved = _boolean(value.get("owner_approved", True), f"{path}.owner_approved", issues)
    evidence = _strings(value.get("evidence", []), f"{path}.evidence", issues)
    if rule_id and not rule_id.startswith("M"):
        issues.append(
            _issue("RULE_ID", "rule_id должен быть versioned mapping ID", f"{path}.rule_id")
        )
    if priority is not None and not 0 <= priority <= 1000:
        issues.append(
            _issue("RULE_PRIORITY", "priority должен быть от 0 до 1000", f"{path}.priority")
        )
    if None in (rule_id, rule_version, priority, scope, clauses, exclusive, approved, evidence):
        return None
    return BusinessRule(
        rule_id, rule_version, scope, clauses, priority, exclusive, approved, evidence
    )


def _parse_scope(value: object, path: str, issues: list[RuleValidationIssue]) -> RuleScope | None:
    if not isinstance(value, dict):
        issues.append(_issue("SCOPE_TYPE", "scope должен быть объектом", path))
        return None
    _unknown_keys(value, _SCOPE_KEYS, path, issues)
    object_scopes = _strings(value.get("object_scopes", []), f"{path}.object_scopes", issues)
    stages = _strings(value.get("stages", []), f"{path}.stages", issues)
    targets = _strings(value.get("target_processes", []), f"{path}.target_processes", issues)
    units = _strings(value.get("source_units", []), f"{path}.source_units", issues)
    if None in (object_scopes, stages, targets, units):
        return None
    return RuleScope(object_scopes, stages, targets, units)


def _parse_clauses(
    value: object, path: str, issues: list[RuleValidationIssue]
) -> tuple[RuleClause, ...] | None:
    if not isinstance(value, list) or not value:
        issues.append(_issue("CLAUSES_TYPE", "clauses должен быть непустым массивом", path))
        return None
    result: list[RuleClause] = []
    for index, item in enumerate(value):
        item_path = f"{path}[{index}]"
        if not isinstance(item, dict):
            issues.append(_issue("CLAUSE_TYPE", "clause должен быть объектом", item_path))
            continue
        _unknown_keys(item, _CLAUSE_KEYS, item_path, issues)
        try:
            action = RuleAction(item.get("action"))
            kind = RuleMatchKind(item.get("match_kind"))
        except ValueError:
            issues.append(_issue("CLAUSE_ENUM", "Недопустимый action или match_kind", item_path))
            continue
        literal = _string(item.get("literal"), f"{item_path}.literal", issues)
        field = _string(item.get("field", "source_work_name"), f"{item_path}.field", issues)
        priority = _integer(item.get("priority", 0), f"{item_path}.priority", issues)
        hard_exclude = _boolean(
            item.get("hard_exclude", False), f"{item_path}.hard_exclude", issues
        )
        if field != "source_work_name":
            issues.append(
                _issue(
                    "CLAUSE_FIELD", "Поддерживается только source_work_name", f"{item_path}.field"
                )
            )
        if literal is not None and _unsafe_text(literal):
            issues.append(
                _issue(
                    "UNSAFE_TEXT",
                    "Исполняемые/внешние конструкции запрещены",
                    f"{item_path}.literal",
                )
            )
        if None not in (literal, field, priority, hard_exclude):
            result.append(RuleClause(action, kind, literal, field, priority, hard_exclude))
    return tuple(result) if result and not issues else None


def _canonical_payload(defaults: RuleDefaults, rules: list[BusinessRule]) -> dict[str, Any]:
    return {
        "configuration_version": "RuleConfigurationVersion-1.0",
        "rule_set_version": "ValidatedRuleSet-10.0",
        "defaults": {
            "coefficient": str(defaults.coefficient),
            "tolerance": str(defaults.tolerance),
            "quantum": str(defaults.quantum),
            "rounding": defaults.rounding,
            "unit_conversion_enabled": defaults.unit_conversion_enabled,
            "source_priority": list(defaults.source_priority),
        },
        "rules": [
            {
                "rule_id": rule.rule_id,
                "rule_version": rule.rule_version,
                "scope": {
                    "object_scopes": list(rule.scope.object_scopes),
                    "stages": list(rule.scope.stages),
                    "target_processes": list(rule.scope.target_processes),
                    "source_units": list(rule.scope.source_units),
                },
                "clauses": [
                    {
                        "action": clause.action.value,
                        "match_kind": clause.match_kind.value,
                        "literal": clause.literal,
                        "field": clause.field,
                        "priority": clause.priority,
                        "hard_exclude": clause.hard_exclude,
                    }
                    for clause in rule.clauses
                ],
                "priority": rule.priority,
                "exclusive_owner": rule.exclusive_owner,
                "owner_approved": rule.owner_approved,
                "evidence": list(rule.evidence),
            }
            for rule in sorted(rules, key=lambda item: item.rule_id)
        ],
    }


def _decimal(
    value: object, path: str, issues: list[RuleValidationIssue], *, positive: bool
) -> Decimal | None:
    if not isinstance(value, str) or not value or "e" in value.casefold() or "," in value:
        issues.append(_issue("DECIMAL_FORMAT", "Decimal должен быть plain string с точкой", path))
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        issues.append(_issue("DECIMAL_FORMAT", "Некорректный Decimal", path))
        return None
    if not parsed.is_finite() or (positive and parsed <= 0) or (not positive and parsed < 0):
        issues.append(
            _issue("DECIMAL_RANGE", "Decimal должен быть конечным и допустимого знака", path)
        )
        return None
    return parsed


def _string(value: object, path: str, issues: list[RuleValidationIssue]) -> str | None:
    if not isinstance(value, str) or not value.strip() or _unsafe_text(value):
        issues.append(_issue("STRING", "Требуется безопасная непустая строка", path))
        return None
    return value


def _strings(value: object, path: str, issues: list[RuleValidationIssue]) -> tuple[str, ...] | None:
    if not isinstance(value, list):
        issues.append(_issue("STRING_LIST", "Требуется массив строк", path))
        return None
    result = tuple(_string(item, f"{path}[{index}]", issues) for index, item in enumerate(value))
    if any(item is None for item in result) or len(set(result)) != len(result):
        issues.append(_issue("STRING_LIST", "Строки должны быть уникальными", path))
        return None
    return tuple(item for item in result if item is not None)


def _integer(value: object, path: str, issues: list[RuleValidationIssue]) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        issues.append(_issue("INTEGER", "Требуется integer без bool/float", path))
        return None
    return value


def _boolean(value: object, path: str, issues: list[RuleValidationIssue]) -> bool | None:
    if not isinstance(value, bool):
        issues.append(_issue("BOOLEAN", "Требуется boolean", path))
        return None
    return value


def _unknown_keys(
    value: dict[str, object], allowed: frozenset[str], path: str, issues: list[RuleValidationIssue]
) -> None:
    for key in sorted(set(value) - allowed):
        issues.append(_issue("UNKNOWN_KEY", f"Неизвестный ключ: {key}", f"{path}.{key}"))


def _unsafe_text(value: str) -> bool:
    lowered = value.casefold()
    return any(marker in lowered for marker in _FORBIDDEN_TEXT)


def _issue(code: str, message: str, path: str) -> RuleValidationIssue:
    return RuleValidationIssue(code, message, path)


def _invalid(code: str, message: str) -> RuleValidationResult:
    return _result(None, [_issue(code, message, "$")])


def _result(
    rule_set: ValidatedRuleSet | None, issues: list[RuleValidationIssue]
) -> RuleValidationResult:
    return RuleValidationResult(rule_set, tuple(issues))
