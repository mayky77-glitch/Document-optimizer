"""Frozen public boundary for Wave 9 shadow acceptance."""

from __future__ import annotations

import ast
import dataclasses
import inspect
from pathlib import Path

from report_processor.reconciliation_patterns import acceptance


def test_shadow_acceptance_contract_version_is_public() -> None:
    assert (
        acceptance.RECONCILIATION_SHADOW_ACCEPTANCE_VERSION == "ReconciliationShadowAcceptance-1.0"
    )


def test_public_models_enums_and_evaluator_are_exact() -> None:
    expected = {
        "OwnerThresholds": {
            "threshold_ref",
            "owner_ref",
            "representative_corpus_ref",
            "independent_holdout_ref",
            "min_recall_at_5",
            "min_mrr",
            "max_top_1_error",
            "max_review_rate",
            "min_pattern_reuse_rate",
            "max_operator_correction_rate",
            "max_suspension_rate",
            "min_availability",
            "max_p95_latency_ns",
            "max_index_size_bytes",
            "fingerprint",
            "version",
        },
        "OperationalEvidence": {
            "status",
            "replay_measurements_fingerprint",
            "recall_at_5",
            "mrr",
            "top_1_error",
            "review_rate",
            "pattern_reuse_rate",
            "operator_correction_rate",
            "suspension_rate",
            "availability",
            "p95_latency_ns",
            "index_size_bytes",
            "fingerprint",
            "version",
        },
        "HardGateEvidence": {
            "replay_fingerprint",
            "source_before_fingerprint",
            "source_after_fingerprint",
            "current_top_level_group_count",
            "repeat_top_level_group_count",
            "disputed_individual_decision_count",
            "forbidden_merge_count",
            "double_membership_count",
            "relevant_nonzero_row_coverage",
            "calculation_mismatch_count",
            "xlsx_mismatch_count",
            "qdrant_outage_authoritative_delta",
            "source_mutation_count",
            "deterministic_repeatability",
            "fingerprint",
            "version",
        },
        "ShadowAcceptanceDecision": {
            "status",
            "reason_codes",
            "replay_fingerprint",
            "promotion_fingerprint",
            "hard_gate_fingerprint",
            "threshold_fingerprint",
            "operational_fingerprint",
            "fingerprint",
            "version",
        },
    }
    public = {
        name: value
        for name, value in vars(acceptance).items()
        if inspect.isclass(value)
        and dataclasses.is_dataclass(value)
        and value.__module__ == acceptance.__name__
    }
    assert set(public) == set(expected)
    for name, names in expected.items():
        assert {field.name for field in dataclasses.fields(public[name])} == names
        assert public[name].__dataclass_params__.frozen and "__slots__" in vars(public[name])
    assert {item.value for item in acceptance.ShadowAcceptanceStatus} == {
        "PASS",
        "FAIL",
        "BLOCKED",
        "UNAVAILABLE",
    }
    assert {item.value for item in acceptance.OperationalEvidenceStatus} == {
        "MEASURED",
        "UNAVAILABLE",
    }
    assert callable(acceptance.evaluate_shadow_acceptance)


def test_module_remains_pure_and_has_no_runtime_or_private_surface() -> None:
    tree = ast.parse(Path(acceptance.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not imported & {
        "openpyxl",
        "pathlib",
        "qdrant",
        "requests",
        "httpx",
        "sqlite3",
        "socket",
        "subprocess",
    }
    text = Path(acceptance.__file__).read_text(encoding="utf-8")
    assert not {
        "ActivationMetadata",
        "pattern_registry",
        "pattern_persistence",
        "admin_panel",
    } & set(text.split())
