"""CLI adapter for validating data-only business-rule configuration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from report_processor.business_rules import load_rule_configuration
from report_processor.cli_json import json_value, write_json


def add_validate_business_rules_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "validate-business-rules", help="Проверить data-only JSON/YAML бизнес-правила"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--log-level", default="INFO")


def run_validate_business_rules(args: argparse.Namespace) -> int:
    result = load_rule_configuration(args.config)
    rule_set = result.rule_set
    canonical = json.loads(rule_set.canonical_json) if rule_set is not None else None
    payload = {
        "valid": result.valid,
        "rule_set": canonical,
        "content_hash": rule_set.content_hash if rule_set is not None else None,
        "issues": json_value(result.issues),
        "conflicts": json_value(result.conflicts.conflicts),
    }
    write_json(payload, args.output)
    return 0 if result.valid else 2
