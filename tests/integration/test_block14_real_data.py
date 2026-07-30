"""Read-only real-workbook evidence for Blocks 8--14."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path

import pytest
from report_processor.quality_control import (
    QualityIssueCode,
    WriteDecision,
    evaluate_quality_control,
)

from report_processor.business_rules import load_default_rule_set
from report_processor.calculation import calculate_matches
from report_processor.matching import match_rows


def _block12_helpers():
    try:
        from test_block12_real_data import _fingerprint, _normalized_source_rows, _target_rows
    except ImportError as exc:  # pragma: no cover - pytest exposes sibling modules
        raise RuntimeError("Block 12 real-data helpers are unavailable") from exc
    return _fingerprint, _normalized_source_rows, _target_rows


def _digest(report: object) -> str:
    payload = {
        "report_id": report.report_id,
        "input_digest": report.input_digest,
        "decision": report.decision.value,
        "issue_ids": [item.issue_id for item in report.issues],
        "matches": report.match_result_ids,
        "calculations": report.calculation_ids,
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def test_real_workbooks_pass_quality_gate_without_mutating_either_input() -> None:
    source_value = os.environ.get("DOCUMENT_OPTIMIZER_REAL_SOURCE_XLSX")
    target_value = os.environ.get("DOCUMENT_OPTIMIZER_REAL_TARGET_XLSX")
    if not source_value or not target_value:
        pytest.skip("real XLSX paths are not set")
    source_path, target_path = Path(source_value), Path(target_value)
    fingerprint, normalized_source_rows, target_rows = _block12_helpers()
    before = (fingerprint(source_path), fingerprint(target_path))
    source_rows = normalized_source_rows(source_path)
    target_result = target_rows(target_path)
    validation = load_default_rule_set()
    assert validation.valid and validation.rule_set is not None
    context = {
        "target_source_id": target_result.schema.source_file_id,
        "target_fingerprint": target_result.schema.source_fingerprint.value,
    }
    matches = match_rows(source_rows, target_result.rows, validation.rule_set, **context)
    calculations = calculate_matches(matches, validation.rule_set)
    first = evaluate_quality_control(matches, calculations, validation.rule_set)
    second = evaluate_quality_control(
        tuple(reversed(matches)), tuple(reversed(calculations)), validation.rule_set
    )

    statuses = Counter(item.status.value for item in matches)
    assert len(source_rows) == 382
    assert len(target_result.rows) == len(matches) == len(calculations) == 107
    assert statuses == {"unmatched": 101, "ambiguous": 5, "matched": 1}
    assert first.decision is WriteDecision.REQUIRE_MANUAL_REVIEW
    assert first.summary.blocking_issue_count == 0
    assert first.report_id == "a49889f3228004ef753e84f16a7fbaee9a6432ec6554bb517b32260c69d2d816"
    assert first.input_digest == "043ad2dfa48b5b31efdc59153f66637aa9ecc21351a1796cfc071b7de087f5a9"
    assert len(first.issues) == 328
    assert all(isinstance(issue.code, QualityIssueCode) for issue in first.issues)
    assert first.report_id == second.report_id
    assert first.input_digest == second.input_digest
    print(json.dumps({"digest": _digest(first), "issues": len(first.issues)}, sort_keys=True))
    assert (fingerprint(source_path), fingerprint(target_path)) == before
