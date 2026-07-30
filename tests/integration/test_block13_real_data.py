"""Read-only real-workbook evidence for the complete Block 8--13 path."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path

import pytest

from report_processor.business_rules import load_default_rule_set
from report_processor.calculation import calculate_matches
from report_processor.matching import match_rows


def _load_block12_helpers():
    """Reuse the reviewed read-only input path, never copying either workbook."""

    try:
        from test_block12_real_data import _fingerprint, _normalized_source_rows, _target_rows
    except ImportError as exc:  # pragma: no cover - pytest always exposes sibling test modules
        raise RuntimeError("Block 12 real-data helpers are unavailable") from exc
    return _fingerprint, _normalized_source_rows, _target_rows


def _digest(results: tuple[object, ...]) -> str:
    payload = [
        {
            "calculation_id": item.calculation_id,
            "target_row_id": item.target_row_id,
            "match_result_id": item.match_result_id,
            "status": item.status.value,
            "quantity": str(item.quantity),
            "cost_before_coefficient": str(item.cost_before_coefficient),
            "cost": str(item.cost),
            "trace": item.trace.trace_id,
            "contributions": [
                {
                    "id": contribution.contribution_id,
                    "source": contribution.source_row_id,
                    "category": contribution.category.value,
                    "raw_quantity": str(contribution.raw_quantity),
                    "raw_cost": str(contribution.raw_cost),
                }
                for contribution in item.trace.contributions
            ],
        }
        for item in results
    ]
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def test_real_workbooks_run_calculation_deterministically_without_mutation() -> None:
    source_value = os.environ.get("DOCUMENT_OPTIMIZER_REAL_SOURCE_XLSX")
    target_value = os.environ.get("DOCUMENT_OPTIMIZER_REAL_TARGET_XLSX")
    if not source_value or not target_value:
        pytest.skip("real XLSX paths are not set")
    source_path, target_path = Path(source_value), Path(target_value)
    fingerprint, normalized_source_rows, target_rows = _load_block12_helpers()
    before = (fingerprint(source_path), fingerprint(target_path))

    source_rows = normalized_source_rows(source_path)
    target_result = target_rows(target_path)
    rule_validation = load_default_rule_set()
    assert rule_validation.valid and rule_validation.rule_set is not None
    context = {
        "target_source_id": target_result.schema.source_file_id,
        "target_fingerprint": target_result.schema.source_fingerprint.value,
    }
    matches = match_rows(source_rows, target_result.rows, rule_validation.rule_set, **context)
    first = calculate_matches(matches, rule_validation.rule_set)
    second = calculate_matches(tuple(reversed(matches)), rule_validation.rule_set)

    assert len(source_rows) == 382
    assert len(target_result.rows) == 107
    assert len(matches) == len(first) == len(target_result.rows)
    assert _digest(first) == _digest(second)
    statuses = Counter(item.status.value for item in first)
    categories = Counter(
        contribution.category.value for item in first for contribution in item.trace.contributions
    )
    assert statuses and categories
    assert all(
        contribution.category.value == "unclassified"
        for item in first
        for contribution in item.trace.contributions
    )
    print(
        json.dumps(
            {"statuses": statuses, "categories": categories, "digest": _digest(first)},
            sort_keys=True,
        )
    )
    assert (fingerprint(source_path), fingerprint(target_path)) == before
