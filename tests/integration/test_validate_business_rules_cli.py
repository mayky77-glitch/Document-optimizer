"""CLI wiring contract for the data-only Block 10 validator."""

from __future__ import annotations

import json
from pathlib import Path

from report_processor.cli import main

FIXTURE = Path(__file__).parents[1] / "fixtures" / "business_rules" / "default_rules.json"


def test_validate_business_rules_cli_writes_canonical_result(tmp_path: Path) -> None:
    output = tmp_path / "validated-rules.json"

    code = main(["validate-business-rules", "--config", str(FIXTURE), "--output", str(output)])

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert code == 0
    assert payload["valid"] is True
    assert payload["rule_set"]["rule_set_version"] == "ValidatedRuleSet-10.0"


def test_validate_business_rules_cli_rejects_executable_yaml(tmp_path: Path) -> None:
    unsafe = tmp_path / "unsafe.yaml"
    unsafe.write_text("!python/object {run: os.system}", encoding="utf-8")
    output = tmp_path / "result.json"

    code = main(["validate-business-rules", "--config", str(unsafe), "--output", str(output)])

    assert code != 0
    assert "PARSE_ERROR" in output.read_text(encoding="utf-8")
