"""Frozen public boundary for Wave 5 offline grouping replay."""

from __future__ import annotations

import ast
import dataclasses
import inspect
from pathlib import Path

from report_processor.reconciliation_patterns import replay


def test_versions_public_models_enums_and_api_are_exact() -> None:
    assert (replay.GROUPING_REPLAY_VERSION, replay.GROUPING_PROMOTION_POLICY_VERSION) == (
        "GroupingReplay-1.0",
        "GroupingPromotionPolicy-1.0",
    )
    expected_fields = {
        "Ratio": {"numerator", "denominator"},
        "OracleResult": {"case_count", "mismatch_refs", "oracle_fingerprint", "version"},
        "ReplaySnapshotIdentity": {
            "split",
            "snapshot_ref",
            "manifest_fingerprint",
            "corpus_fingerprint",
            "source_set_refs",
            "document_set_refs",
            "consequential_version_fingerprint",
            "row_count",
            "review_row_count",
            "review_group_count",
            "sealed",
            "seal_ref",
            "fingerprint",
            "version",
        },
        "ReplayObservation": {
            "snapshot_fingerprint",
            "evaluated_head_fingerprint",
            "effective_decision_fingerprint",
            "pattern_decision_refs",
            "correct_decision_refs",
            "covered_row_refs",
            "covered_group_refs",
            "supporting_document_set_refs",
            "contradiction_refs",
            "forbidden_pair_refs",
            "category_change_refs",
            "mode_change_refs",
            "unit_change_refs",
            "decision_mismatch_refs",
            "manual_group_count",
            "manual_action_count",
            "unresolved_row_count",
            "double_membership_count",
            "calculation_oracle",
            "xlsx_oracle",
            "semantic_fingerprint",
            "version",
        },
        "SplitReplayMetrics": {
            "split",
            "snapshot_fingerprint",
            "coverage_rows",
            "coverage_groups",
            "precision",
            "support_document_set_count",
            "contradiction_count",
            "forbidden_merge_count",
            "manual_group_before",
            "manual_group_after",
            "manual_action_before",
            "manual_action_after",
            "unresolved_before",
            "unresolved_after",
            "changed_category_count",
            "changed_mode_count",
            "changed_unit_count",
            "decision_mismatch_count",
            "double_membership_count",
            "calculation_mismatch_count",
            "xlsx_mismatch_count",
            "before_semantic_fingerprint",
            "after_semantic_fingerprint",
            "repeat_semantic_fingerprint",
            "fingerprint",
            "version",
        },
        "IndexMeasurement": {
            "status",
            "environment_ref",
            "index_ref",
            "size_bytes",
            "fingerprint",
            "version",
        },
        "ReplayMeasurements": {
            "latency_samples_ns",
            "p50_latency_ns",
            "p95_latency_ns",
            "index",
            "fingerprint",
            "version",
        },
        "PromotionPolicy": {
            "policy_ref",
            "owner_ref",
            "approval_ref",
            "release_window_ref",
            "allowed_kinds",
            "allowed_scope_fingerprints",
            "min_support_document_sets",
            "min_holdout_document_sets",
            "min_holdout_decisions",
            "min_coverage_rows",
            "min_coverage_groups",
            "min_precision",
            "max_manual_group_count",
            "max_manual_action_count",
            "max_unresolved_row_count",
            "max_p95_latency_ns",
            "index_required",
            "max_index_size_bytes",
            "fingerprint",
            "version",
        },
        "GroupingReplayReport": {
            "evaluated_pattern_id",
            "evaluated_head_fingerprint",
            "policy_fingerprint",
            "baseline_snapshot_fingerprint",
            "holdout_snapshot_fingerprint",
            "baseline_metrics",
            "holdout_metrics",
            "deterministic_repeatability",
            "semantic_fingerprint",
            "measurements",
            "fingerprint",
            "version",
        },
        "PromotionDecision": {
            "verdict",
            "reason_codes",
            "report_fingerprint",
            "policy_fingerprint",
            "head_fingerprint",
            "fingerprint",
            "version",
        },
    }
    public = {
        name: value
        for name, value in vars(replay).items()
        if inspect.isclass(value)
        and dataclasses.is_dataclass(value)
        and value.__module__ == replay.__name__
    }
    assert set(public) == set(expected_fields)
    for name, fields in expected_fields.items():
        assert {field.name for field in dataclasses.fields(public[name])} == fields
        assert public[name].__dataclass_params__.frozen and "__slots__" in vars(public[name])
    assert {item.value for item in replay.ReplaySplit} == {"baseline", "holdout"}
    assert {item.value for item in replay.PromotionVerdict} == {
        "stop",
        "shadow_eligible",
        "owner_approval_required",
        "activation_eligible",
    }
    assert {item.value for item in replay.MeasurementStatus} == {
        "measured",
        "not_applicable",
        "unavailable",
    }
    for name in (
        "run_grouping_replay",
        "evaluate_shadow",
        "evaluate_promotion",
        "owner_approval_ref",
        "build_activation_metadata",
    ):
        assert callable(getattr(replay, name))


def test_replay_module_has_no_forbidden_runtime_imports_or_raw_data_surface() -> None:
    tree = ast.parse(Path(replay.__file__).read_text(encoding="utf-8"))
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not imports & {
        "openpyxl",
        "qdrant",
        "sqlite3",
        "requests",
        "httpx",
        "socket",
        "subprocess",
        "pathlib",
    }
    annotations = " ".join(
        ast.unparse(node.annotation)
        for node in ast.walk(tree)
        if isinstance(node, ast.arg) and node.annotation
    )
    assert not {"Path", "Workbook", "Document", "Row"} & set(
        annotations.replace("[", " ").replace("]", " ").replace("|", " ").split()
    )
