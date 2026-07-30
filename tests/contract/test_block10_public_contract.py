"""Frozen public contract for data-only business rules (Block 10)."""

from __future__ import annotations

from report_processor.business_rules import (
    RuleConfigurationVersion,
    RulePrecedence,
    ValidatedRuleSet,
    detect_rule_conflicts,
    load_default_rule_set,
    load_rule_configuration,
    validate_rule_payload,
)


def test_block10_public_api_is_importable_and_default_records_are_versioned() -> None:
    result = load_default_rule_set()

    assert result.valid
    assert isinstance(result.rule_set, ValidatedRuleSet)
    assert isinstance(result.rule_set.configuration_version, RuleConfigurationVersion)
    assert result.rule_set.defaults.source_priority == ("ks6a",)
    assert RulePrecedence.HARD_EXCLUDE.value == "hard_exclude"
    assert tuple(rule.rule_id for rule in result.rule_set.rules) == tuple(
        f"M{number:02d}" for number in range(1, 16)
    )
    assert callable(validate_rule_payload)
    assert callable(load_rule_configuration)
    assert callable(detect_rule_conflicts)
