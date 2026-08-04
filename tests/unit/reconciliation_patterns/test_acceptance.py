"""Adversarial evaluation tests for Wave 9 shadow acceptance."""

from __future__ import annotations

import dataclasses
import hashlib

import pytest

from report_processor.reconciliation_patterns import acceptance, replay
from report_processor.reconciliation_patterns.pattern_models import PatternRegistryError


def _hash(name: str) -> str:
    return "sha256:" + hashlib.sha256(name.encode()).hexdigest()


def _sealed(cls: type[object], values: dict[str, object]) -> object:
    return cls(**values, fingerprint=replay.replay_fingerprint(values))  # type: ignore[operator]


def _metric(split: replay.ReplaySplit, name: str) -> replay.SplitReplayMetrics:
    values: dict[str, object] = {
        "split": split,
        "snapshot_fingerprint": _hash(name + "-snapshot"),
        "coverage_rows": replay.Ratio(1, 1),
        "coverage_groups": replay.Ratio(1, 1),
        "precision": replay.Ratio(1, 1),
        "support_document_set_count": 2,
        "contradiction_count": 0,
        "forbidden_merge_count": 0,
        "manual_group_before": 2,
        "manual_group_after": 1,
        "manual_action_before": 2,
        "manual_action_after": 1,
        "unresolved_before": 1,
        "unresolved_after": 0,
        "changed_category_count": 0,
        "changed_mode_count": 0,
        "changed_unit_count": 0,
        "decision_mismatch_count": 0,
        "double_membership_count": 0,
        "calculation_mismatch_count": 0,
        "xlsx_mismatch_count": 0,
        "before_semantic_fingerprint": _hash(name + "-before"),
        "after_semantic_fingerprint": _hash(name + "-after"),
        "repeat_semantic_fingerprint": _hash(name + "-after"),
        "version": replay.GROUPING_REPLAY_VERSION,
    }
    return _sealed(replay.SplitReplayMetrics, values)  # type: ignore[return-value]


def _report() -> replay.GroupingReplayReport:
    index_values = {
        "status": replay.MeasurementStatus.MEASURED,
        "environment_ref": _hash("environment"),
        "index_ref": _hash("index"),
        "size_bytes": 8,
        "version": replay.GROUPING_REPLAY_VERSION,
    }
    index = _sealed(replay.IndexMeasurement, index_values)
    measurement_values = {
        "latency_samples_ns": (3, 7),
        "p50_latency_ns": 3,
        "p95_latency_ns": 7,
        "index": index,
        "version": replay.GROUPING_REPLAY_VERSION,
    }
    measurements = _sealed(replay.ReplayMeasurements, measurement_values)
    baseline, holdout = (
        _metric(replay.ReplaySplit.BASELINE, "base"),
        _metric(replay.ReplaySplit.HOLDOUT, "hold"),
    )
    values = {
        "evaluated_pattern_id": _hash("pattern"),
        "evaluated_head_fingerprint": _hash("head"),
        "policy_fingerprint": _hash("policy"),
        "baseline_snapshot_fingerprint": baseline.snapshot_fingerprint,
        "holdout_snapshot_fingerprint": holdout.snapshot_fingerprint,
        "baseline_metrics": baseline,
        "holdout_metrics": holdout,
        "deterministic_repeatability": True,
        "semantic_fingerprint": replay.replay_fingerprint(
            {
                "evaluated_pattern_id": _hash("pattern"),
                "evaluated_head_fingerprint": _hash("head"),
                "policy_fingerprint": _hash("policy"),
                "baseline_snapshot_fingerprint": baseline.snapshot_fingerprint,
                "holdout_snapshot_fingerprint": holdout.snapshot_fingerprint,
                "baseline_metrics": baseline,
                "holdout_metrics": holdout,
                "deterministic_repeatability": True,
                "version": replay.GROUPING_REPLAY_VERSION,
            }
        ),
        "measurements": measurements,
        "version": replay.GROUPING_REPLAY_VERSION,
    }
    return _sealed(replay.GroupingReplayReport, values)  # type: ignore[return-value]


def _thresholds() -> acceptance.OwnerThresholds:
    values: dict[str, object] = {
        "threshold_ref": _hash("threshold"),
        "owner_ref": _hash("owner"),
        "representative_corpus_ref": _hash("corpus"),
        "independent_holdout_ref": _hash("holdout"),
        "min_recall_at_5": replay.Ratio(4, 5),
        "min_mrr": replay.Ratio(3, 4),
        "max_top_1_error": replay.Ratio(1, 5),
        "max_review_rate": replay.Ratio(1, 4),
        "min_pattern_reuse_rate": replay.Ratio(1, 2),
        "max_operator_correction_rate": replay.Ratio(1, 4),
        "max_suspension_rate": replay.Ratio(1, 5),
        "min_availability": replay.Ratio(9, 10),
        "max_p95_latency_ns": 8,
        "max_index_size_bytes": 9,
        "version": acceptance.RECONCILIATION_SHADOW_ACCEPTANCE_VERSION,
    }
    return _sealed(acceptance.OwnerThresholds, values)  # type: ignore[return-value]


def _input() -> tuple[
    replay.GroupingReplayReport,
    replay.PromotionDecision,
    acceptance.HardGateEvidence,
    acceptance.OwnerThresholds,
    acceptance.OperationalEvidence,
]:
    report, thresholds = _report(), _thresholds()
    promotion_values = {
        "verdict": replay.PromotionVerdict.OWNER_APPROVAL_REQUIRED,
        "reason_codes": (),
        "report_fingerprint": report.fingerprint,
        "policy_fingerprint": report.policy_fingerprint,
        "head_fingerprint": report.evaluated_head_fingerprint,
        "version": replay.GROUPING_REPLAY_VERSION,
    }
    promotion = _sealed(replay.PromotionDecision, promotion_values)
    gate_values: dict[str, object] = {
        "replay_fingerprint": report.fingerprint,
        "source_before_fingerprint": _hash("source"),
        "source_after_fingerprint": _hash("source"),
        "current_top_level_group_count": 50,
        "repeat_top_level_group_count": 30,
        "disputed_individual_decision_count": 20,
        "forbidden_merge_count": 0,
        "double_membership_count": 0,
        "relevant_nonzero_row_coverage": replay.Ratio(1, 1),
        "calculation_mismatch_count": 0,
        "xlsx_mismatch_count": 0,
        "qdrant_outage_authoritative_delta": 0,
        "source_mutation_count": 0,
        "deterministic_repeatability": True,
        "version": acceptance.RECONCILIATION_SHADOW_ACCEPTANCE_VERSION,
    }
    gates = _sealed(acceptance.HardGateEvidence, gate_values)
    operational_values: dict[str, object] = {
        "status": acceptance.OperationalEvidenceStatus.MEASURED,
        "replay_measurements_fingerprint": report.measurements.fingerprint,
        "recall_at_5": replay.Ratio(4, 5),
        "mrr": replay.Ratio(3, 4),
        "top_1_error": replay.Ratio(1, 5),
        "review_rate": replay.Ratio(1, 4),
        "pattern_reuse_rate": replay.Ratio(1, 2),
        "operator_correction_rate": replay.Ratio(1, 4),
        "suspension_rate": replay.Ratio(1, 5),
        "availability": replay.Ratio(9, 10),
        "p95_latency_ns": 7,
        "index_size_bytes": 8,
        "version": acceptance.RECONCILIATION_SHADOW_ACCEPTANCE_VERSION,
    }
    operational = _sealed(acceptance.OperationalEvidence, operational_values)
    return report, promotion, gates, thresholds, operational  # type: ignore[return-value]


def test_pass_requires_every_exact_hard_gate_and_owner_threshold() -> None:
    report, promotion, gates, thresholds, operational = _input()
    decision = acceptance.evaluate_shadow_acceptance(
        report, promotion, gates, thresholds, operational
    )
    assert decision.status is acceptance.ShadowAcceptanceStatus.PASS
    assert not decision.reason_codes
    changed_gates = {
        field.name: getattr(gates, field.name)
        for field in dataclasses.fields(gates)
        if field.name != "fingerprint"
    }
    changed_gates["qdrant_outage_authoritative_delta"] = 1
    failed = acceptance.evaluate_shadow_acceptance(
        report,
        promotion,
        _sealed(acceptance.HardGateEvidence, changed_gates),
        thresholds,
        operational,
    )
    assert failed.status is acceptance.ShadowAcceptanceStatus.FAIL
    assert failed.reason_codes == ("OUTAGE_DELTA_PRESENT",)


def test_missing_thresholds_blocks_and_unavailable_dependency_never_passes() -> None:
    report, promotion, gates, _, operational = _input()
    blocked = acceptance.evaluate_shadow_acceptance(report, promotion, gates, None, operational)
    assert blocked.status is acceptance.ShadowAcceptanceStatus.BLOCKED
    assert blocked.reason_codes == ("OWNER_THRESHOLDS_MISSING",)
    unavailable_values = {
        "status": acceptance.OperationalEvidenceStatus.UNAVAILABLE,
        "replay_measurements_fingerprint": None,
        "recall_at_5": None,
        "mrr": None,
        "top_1_error": None,
        "review_rate": None,
        "pattern_reuse_rate": None,
        "operator_correction_rate": None,
        "suspension_rate": None,
        "availability": None,
        "p95_latency_ns": None,
        "index_size_bytes": None,
        "version": acceptance.RECONCILIATION_SHADOW_ACCEPTANCE_VERSION,
    }
    unavailable = _sealed(acceptance.OperationalEvidence, unavailable_values)
    decision = acceptance.evaluate_shadow_acceptance(
        report, promotion, gates, _thresholds(), unavailable
    )
    assert decision.status is acceptance.ShadowAcceptanceStatus.UNAVAILABLE
    assert decision.reason_codes == ("DEPENDENCY_UNAVAILABLE",)


def test_forged_values_and_raw_or_unbounded_values_fail_closed() -> None:
    _, _, _, thresholds, _ = _input()
    with pytest.raises(PatternRegistryError) as error:
        dataclasses.replace(thresholds, owner_ref="owner@example.com")
    assert error.value.code == "ACCEPTANCE_SCHEMA_INVALID"
    with pytest.raises(PatternRegistryError) as error:
        dataclasses.replace(thresholds, fingerprint=_hash("forged"))
    assert error.value.code == "ACCEPTANCE_FINGERPRINT_MISMATCH"
    with pytest.raises(PatternRegistryError) as error:
        acceptance.evaluate_shadow_acceptance(object(), None, None, None, None)  # type: ignore[arg-type]
    assert error.value.code == "ACCEPTANCE_SCHEMA_INVALID"
