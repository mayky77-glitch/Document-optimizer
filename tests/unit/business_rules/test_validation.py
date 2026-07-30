"""Unit coverage for strict, deterministic business-rule validation."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest

from report_processor.business_rules import (
    detect_rule_conflicts,
    load_default_rule_set,
    load_rule_configuration,
    validate_rule_payload,
)

FIXTURES = Path(__file__).parents[2] / "fixtures" / "business_rules"


def _payload() -> dict[str, object]:
    return json.loads((FIXTURES / "default_rules.json").read_text(encoding="utf-8"))


def _issue_codes(result) -> set[str]:
    return {issue.code for issue in result.issues}


def test_json_and_yaml_have_identical_canonical_rule_set() -> None:
    json_result = load_rule_configuration(FIXTURES / "default_rules.json")
    yaml_result = load_rule_configuration(FIXTURES / "default_rules.yaml")

    assert json_result.valid and yaml_result.valid
    assert json_result.rule_set.canonical_json == yaml_result.rule_set.canonical_json
    assert json_result.rule_set.content_hash == yaml_result.rule_set.content_hash
    assert (
        json_result.rule_set.content_hash
        == hashlib.sha256(json_result.rule_set.canonical_json).hexdigest()
    )
    assert json_result.rule_set.defaults.source_priority == ("ks6a",)
    assert json_result.rule_set.defaults.allowed_units == ("шт",)
    assert json_result.rule_set.defaults.default_run_coefficient == Decimal("2.7")


def test_canonical_bytes_are_compact_sorted_utf8_and_rules_are_deterministic() -> None:
    payload = _payload()
    second = deepcopy(payload["rules"][0])
    second["rule_id"] = "M02"
    payload["rules"] = [second, payload["rules"][0]]

    result = validate_rule_payload(payload)

    assert result.valid
    assert result.rule_set.canonical_json == json.dumps(
        json.loads(result.rule_set.canonical_json),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert [rule.rule_id for rule in result.rule_set.rules] == ["M01", "M02"]


@pytest.mark.parametrize(
    ("path", "content", "expected_code"),
    [
        (
            "duplicate.json",
            '{"configuration_version":"x","configuration_version":"x"}',
            "PARSE_ERROR",
        ),
        ("tag.yaml", "!python/object {danger: true}", "PARSE_ERROR"),
        ("anchor.yaml", "value: &a safe\ncopy: *a", "PARSE_ERROR"),
        ("duplicate.yaml", "rules: []\nrules: []", "PARSE_ERROR"),
        ("bad.txt", "{}", "PARSE_ERROR"),
    ],
)
def test_loader_rejects_duplicate_keys_and_non_data_yaml(
    tmp_path: Path, path: str, content: str, expected_code: str
) -> None:
    config = tmp_path / path
    config.write_text(content, encoding="utf-8")

    result = load_rule_configuration(config)

    assert not result.valid
    assert expected_code in _issue_codes(result)


@pytest.mark.parametrize(
    ("mutate", "expected_code"),
    [
        (lambda value: value.update(unexpected=True), "UNKNOWN_KEY"),
        (lambda value: value["defaults"].update(default_run_coefficient="1e2"), "DECIMAL_FORMAT"),
        (
            lambda value: value["defaults"].update(cost_tolerance_ratio=float("nan")),
            "DECIMAL_FORMAT",
        ),
        (lambda value: value["rules"][0].update(priority=True), "INTEGER"),
        (lambda value: value["rules"][0]["scope"].update(source_units=["шт", "шт"]), "STRING_LIST"),
        (
            lambda value: value["rules"][0]["clauses"][0].update(literal="${ENV:SECRET}"),
            "UNSAFE_TEXT",
        ),
        (
            lambda value: value["rules"][0]["clauses"][0].update(literal="eval(import os)"),
            "UNSAFE_TEXT",
        ),
    ],
)
def test_validator_rejects_unknown_unsafe_and_noncanonical_values(
    mutate, expected_code: str
) -> None:
    payload = _payload()
    mutate(payload)

    result = validate_rule_payload(payload)

    assert not result.valid
    assert expected_code in _issue_codes(result)


def test_validator_enforces_depth_and_rule_count_limits() -> None:
    too_deep: object = "x"
    for _ in range(33):
        too_deep = [too_deep]
    payload = _payload()
    payload["rules"] = too_deep

    deep_result = validate_rule_payload(payload)
    assert not deep_result.valid
    assert "INVALID_STRUCTURE" in _issue_codes(deep_result)

    many_payload = _payload()
    many_payload["rules"] = [deepcopy(many_payload["rules"][0]) for _ in range(1001)]
    many_result = validate_rule_payload(many_payload)
    assert not many_result.valid
    assert "RULE_LIMIT" in _issue_codes(many_result)


def test_conflicts_are_reported_for_duplicate_and_exclusive_overlaps() -> None:
    payload = _payload()
    duplicate = deepcopy(payload["rules"][0])
    duplicate["exclusive_owner"] = True
    payload["rules"][0]["exclusive_owner"] = True
    payload["rules"].append(duplicate)

    result = validate_rule_payload(payload)

    assert not result.valid
    assert result.rule_set is None
    default_result = load_default_rule_set()
    assert default_result.valid
    assert detect_rule_conflicts(default_result.rule_set).valid


def test_m12_is_conditioned_on_source_unit() -> None:
    result = load_default_rule_set()

    assert result.valid
    m12 = next(rule for rule in result.rule_set.rules if rule.rule_id == "M12")
    assert m12.scope.source_units == ("шт.",)
