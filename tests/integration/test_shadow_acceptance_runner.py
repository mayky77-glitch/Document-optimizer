"""Adversarial integration checks for the offline shadow-acceptance runner."""

from __future__ import annotations

import dataclasses

import pytest

from report_processor.reconciliation_patterns import acceptance, acceptance_runner, replay


def _ref(value: str) -> str:
    return "sha256:" + value.zfill(64)


def _sealed(cls: type[object], values: dict[str, object]) -> object:
    return cls(**values, fingerprint=replay.replay_fingerprint(values))


def _replace_sealed(value: object, **changes: object) -> object:
    values = {
        field.name: getattr(value, field.name)
        for field in dataclasses.fields(value)
        if field.name != "fingerprint"
    }
    values.update(changes)
    return _sealed(type(value), values)


def _snapshot(split: replay.ReplaySplit, suffix: str) -> replay.ReplaySnapshotIdentity:
    values: dict[str, object] = {
        "split": split,
        "snapshot_ref": _ref("10" + suffix),
        "manifest_fingerprint": _ref("11" + suffix),
        "corpus_fingerprint": _ref("12" + suffix),
        "source_set_refs": (_ref("13" + suffix),),
        "document_set_refs": (_ref("14" + suffix),),
        "consequential_version_fingerprint": _ref("15"),
        "row_count": 2,
        "review_row_count": 2,
        "review_group_count": 1,
        "sealed": True,
        "seal_ref": _ref("16" + suffix),
        "version": replay.GROUPING_REPLAY_VERSION,
    }
    return _sealed(replay.ReplaySnapshotIdentity, values)  # type: ignore[return-value]


def _report(
    baseline: replay.ReplaySnapshotIdentity, holdout: replay.ReplaySnapshotIdentity
) -> replay.GroupingReplayReport:
    def metric(snapshot: replay.ReplaySnapshotIdentity) -> replay.SplitReplayMetrics:
        suffix = "1" if snapshot.split is replay.ReplaySplit.BASELINE else "2"
        values: dict[str, object] = {
            "split": snapshot.split,
            "snapshot_fingerprint": snapshot.fingerprint,
            "coverage_rows": replay.Ratio(1, 1),
            "coverage_groups": replay.Ratio(1, 1),
            "precision": replay.Ratio(1, 1),
            "support_document_set_count": 1,
            "contradiction_count": 0,
            "forbidden_merge_count": 0,
            "manual_group_before": 1,
            "manual_group_after": 1,
            "manual_action_before": 1,
            "manual_action_after": 1,
            "unresolved_before": 0,
            "unresolved_after": 0,
            "changed_category_count": 0,
            "changed_mode_count": 0,
            "changed_unit_count": 0,
            "decision_mismatch_count": 0,
            "double_membership_count": 0,
            "calculation_mismatch_count": 0,
            "xlsx_mismatch_count": 0,
            "before_semantic_fingerprint": _ref("20" + suffix),
            "after_semantic_fingerprint": _ref("21" + suffix),
            "repeat_semantic_fingerprint": _ref("21" + suffix),
            "version": replay.GROUPING_REPLAY_VERSION,
        }
        return _sealed(replay.SplitReplayMetrics, values)  # type: ignore[return-value]

    index_values: dict[str, object] = {
        "status": replay.MeasurementStatus.MEASURED,
        "environment_ref": _ref("30"),
        "index_ref": _ref("31"),
        "size_bytes": 10,
        "version": replay.GROUPING_REPLAY_VERSION,
    }
    index = _sealed(replay.IndexMeasurement, index_values)
    measurement_values: dict[str, object] = {
        "latency_samples_ns": (1, 2, 3, 4),
        "p50_latency_ns": 2,
        "p95_latency_ns": 4,
        "index": index,
        "version": replay.GROUPING_REPLAY_VERSION,
    }
    measurements = _sealed(replay.ReplayMeasurements, measurement_values)
    semantic_values: dict[str, object] = {
        "evaluated_pattern_id": _ref("40"),
        "evaluated_head_fingerprint": _ref("41"),
        "policy_fingerprint": _ref("42"),
        "baseline_snapshot_fingerprint": baseline.fingerprint,
        "holdout_snapshot_fingerprint": holdout.fingerprint,
        "baseline_metrics": metric(baseline),
        "holdout_metrics": metric(holdout),
        "deterministic_repeatability": True,
        "version": replay.GROUPING_REPLAY_VERSION,
    }
    semantic = replay.replay_fingerprint(semantic_values)
    values = {**semantic_values, "semantic_fingerprint": semantic, "measurements": measurements}
    return _sealed(replay.GroupingReplayReport, values)  # type: ignore[return-value]


def _inputs() -> acceptance_runner.ShadowAcceptanceInputs:
    baseline, holdout = (
        _snapshot(replay.ReplaySplit.BASELINE, "1"),
        _snapshot(replay.ReplaySplit.HOLDOUT, "2"),
    )
    report = _report(baseline, holdout)
    promotion_values: dict[str, object] = {
        "verdict": replay.PromotionVerdict.OWNER_APPROVAL_REQUIRED,
        "reason_codes": (),
        "report_fingerprint": report.fingerprint,
        "policy_fingerprint": report.policy_fingerprint,
        "head_fingerprint": report.evaluated_head_fingerprint,
        "version": replay.GROUPING_REPLAY_VERSION,
    }
    promotion = _sealed(replay.PromotionDecision, promotion_values)
    source_values: dict[str, object] = {
        "before_fingerprint": _ref("50"),
        "after_fingerprint": _ref("50"),
        "mutation_count": 0,
        "before_manifest_fingerprint": baseline.manifest_fingerprint,
        "after_manifest_fingerprint": holdout.manifest_fingerprint,
        "before_source_set_fingerprint": replay.replay_fingerprint(baseline.source_set_refs),
        "after_source_set_fingerprint": replay.replay_fingerprint(holdout.source_set_refs),
        "version": acceptance_runner.SHADOW_ACCEPTANCE_RUNNER_VERSION,
    }
    source = _sealed(acceptance_runner.SourceIntegrityEvidence, source_values)
    outage_values: dict[str, object] = {
        "qdrant_unavailable": True,
        "authoritative_decision_delta": 0,
        "oracle_fingerprint": replay.replay_fingerprint(
            {
                "qdrant_unavailable": True,
                "authoritative_decision_delta": 0,
                "version": acceptance_runner.SHADOW_ACCEPTANCE_RUNNER_VERSION,
            }
        ),
        "version": acceptance_runner.SHADOW_ACCEPTANCE_RUNNER_VERSION,
    }
    outage = _sealed(acceptance_runner.OutageDecisionDelta, outage_values)
    gate_values: dict[str, object] = {
        "replay_fingerprint": report.fingerprint,
        "source_before_fingerprint": source.before_fingerprint,
        "source_after_fingerprint": source.after_fingerprint,
        "group_action_observation_fingerprint": replay.replay_fingerprint(
            {
                "baseline": report.baseline_metrics.fingerprint,
                "holdout": report.holdout_metrics.fingerprint,
                "current_groups": 1,
                "repeat_groups": 1,
                "disputed_decisions": 0,
            }
        ),
        "outage_oracle_fingerprint": outage.oracle_fingerprint,
        "current_top_level_group_count": 1,
        "repeat_top_level_group_count": 1,
        "disputed_individual_decision_count": 0,
        "contradiction_count": 0,
        "decision_mismatch_count": 0,
        "forbidden_merge_count": 0,
        "double_membership_count": 0,
        "relevant_nonzero_row_coverage": replay.Ratio(1, 1),
        "calculation_mismatch_count": 0,
        "xlsx_mismatch_count": 0,
        "qdrant_outage_authoritative_delta": outage.authoritative_decision_delta,
        "source_mutation_count": source.mutation_count,
        "deterministic_repeatability": True,
        "version": acceptance.RECONCILIATION_SHADOW_ACCEPTANCE_VERSION,
    }
    gates = _sealed(acceptance.HardGateEvidence, gate_values)
    thresholds_values: dict[str, object] = {
        "threshold_ref": _ref("60"),
        "owner_ref": _ref("61"),
        "representative_corpus_ref": baseline.corpus_fingerprint,
        "independent_holdout_ref": holdout.corpus_fingerprint,
        "representative_snapshot_fingerprint": baseline.fingerprint,
        "independent_holdout_snapshot_fingerprint": holdout.fingerprint,
        "min_recall_at_5": replay.Ratio(1, 2),
        "min_mrr": replay.Ratio(1, 2),
        "max_top_1_error": replay.Ratio(1, 2),
        "max_review_rate": replay.Ratio(1, 2),
        "min_pattern_reuse_rate": replay.Ratio(1, 2),
        "max_operator_correction_rate": replay.Ratio(1, 2),
        "max_suspension_rate": replay.Ratio(1, 2),
        "min_availability": replay.Ratio(1, 2),
        "max_p95_latency_ns": 5,
        "max_index_size_bytes": 11,
        "version": acceptance.RECONCILIATION_SHADOW_ACCEPTANCE_VERSION,
    }
    thresholds = _sealed(acceptance.OwnerThresholds, thresholds_values)
    operational_values: dict[str, object] = {
        "status": acceptance.OperationalEvidenceStatus.MEASURED,
        "replay_measurements_fingerprint": report.measurements.fingerprint,
        "observation_fingerprint": _ref("64"),
        "recall_at_5": replay.Ratio(1, 1),
        "mrr": replay.Ratio(1, 1),
        "top_1_error": replay.Ratio(0, 1),
        "review_rate": replay.Ratio(0, 1),
        "pattern_reuse_rate": replay.Ratio(1, 1),
        "operator_correction_rate": replay.Ratio(0, 1),
        "suspension_rate": replay.Ratio(0, 1),
        "availability": replay.Ratio(1, 1),
        "p95_latency_ns": 4,
        "index_size_bytes": 10,
        "version": acceptance.RECONCILIATION_SHADOW_ACCEPTANCE_VERSION,
    }
    operational = _sealed(acceptance.OperationalEvidence, operational_values)
    operational = _replace_sealed(
        operational,
        observation_fingerprint=acceptance_runner._operational_observation_fingerprint(
            operational, outage
        ),
    )
    values: dict[str, object] = {
        "baseline": baseline,
        "holdout": holdout,
        "report": report,
        "promotion": promotion,
        "gates": gates,
        "thresholds": thresholds,
        "operational": operational,
        "source": source,
        "outage": outage,
        "version": acceptance_runner.SHADOW_ACCEPTANCE_RUNNER_VERSION,
    }
    return _sealed(acceptance_runner.ShadowAcceptanceInputs, values)  # type: ignore[return-value]


def test_runner_binds_controlled_evidence_and_delegates_to_injected_evaluator() -> None:
    inputs = _inputs()
    # P6: each independently sealed evidence source must carry its own
    # provenance identity; a self-consistent aggregate is not sufficient.
    assert hasattr(inputs.thresholds, "representative_snapshot_fingerprint")
    assert hasattr(inputs.operational, "observation_fingerprint")
    assert hasattr(inputs.gates, "group_action_observation_fingerprint")
    assert hasattr(inputs.outage, "oracle_fingerprint")
    calls: list[tuple[object, ...]] = []

    def evaluator(*values: object) -> acceptance.ShadowAcceptanceDecision:
        calls.append(values)
        return acceptance.evaluate_shadow_acceptance(*values)  # type: ignore[arg-type]

    result = acceptance_runner.ShadowAcceptanceRunner(evaluator).run(inputs)
    assert result.status is acceptance.ShadowAcceptanceStatus.PASS
    assert calls == [
        (inputs.report, inputs.promotion, inputs.gates, inputs.thresholds, inputs.operational)
    ]


@pytest.mark.parametrize("field", ("baseline", "source", "outage"))
def test_runner_rejects_mismatched_or_unavailable_bound_evidence(field: str) -> None:
    inputs = _inputs()
    if field == "baseline":
        changed = _replace_sealed(inputs, baseline=inputs.holdout)
    elif field == "source":
        changed_source = _replace_sealed(inputs.source, after_fingerprint=_ref("51"))
        changed = _replace_sealed(inputs, source=changed_source)
    else:
        changed_outage = _replace_sealed(
            inputs.outage,
            authoritative_decision_delta=1,
            oracle_fingerprint=replay.replay_fingerprint(
                {
                    "qdrant_unavailable": True,
                    "authoritative_decision_delta": 1,
                    "version": acceptance_runner.SHADOW_ACCEPTANCE_RUNNER_VERSION,
                }
            ),
        )
        changed = _replace_sealed(inputs, outage=changed_outage)
    with pytest.raises(acceptance_runner.ShadowAcceptanceRunnerError):
        acceptance_runner.ShadowAcceptanceRunner(acceptance.evaluate_shadow_acceptance).run(changed)


def test_source_evidence_rejects_matching_raw_path_and_outage_must_be_proven() -> None:
    inputs = _inputs()
    raw_source_values = {
        "before_fingerprint": "/confidential/source.xlsx",
        "after_fingerprint": "/confidential/source.xlsx",
        "mutation_count": 0,
        "before_manifest_fingerprint": _ref("52"),
        "after_manifest_fingerprint": _ref("53"),
        "before_source_set_fingerprint": _ref("54"),
        "after_source_set_fingerprint": _ref("55"),
        "version": acceptance_runner.SHADOW_ACCEPTANCE_RUNNER_VERSION,
    }
    with pytest.raises(acceptance_runner.ShadowAcceptanceRunnerError):
        _sealed(acceptance_runner.SourceIntegrityEvidence, raw_source_values)
    no_outage = _replace_sealed(
        inputs.outage,
        qdrant_unavailable=False,
        oracle_fingerprint=replay.replay_fingerprint(
            {
                "qdrant_unavailable": False,
                "authoritative_decision_delta": 0,
                "version": acceptance_runner.SHADOW_ACCEPTANCE_RUNNER_VERSION,
            }
        ),
    )
    changed = _replace_sealed(inputs, outage=no_outage)
    with pytest.raises(acceptance_runner.ShadowAcceptanceRunnerError):
        acceptance_runner.ShadowAcceptanceRunner(acceptance.evaluate_shadow_acceptance).run(changed)


def test_runner_refuses_mutation_and_preserves_repeat_equivalence() -> None:
    inputs = _inputs()
    before = repr(inputs)
    runner = acceptance_runner.ShadowAcceptanceRunner(acceptance.evaluate_shadow_acceptance)
    assert runner.run(inputs) == runner.run(inputs)
    assert repr(inputs) == before
    changed_gates = _replace_sealed(inputs.gates, calculation_mismatch_count=1)
    changed = _replace_sealed(inputs, gates=changed_gates)
    decision = runner.run(changed)
    assert decision.status is acceptance.ShadowAcceptanceStatus.FAIL
    assert "HARD_GATE_METRICS_MISMATCH" in decision.reason_codes
    assert "CALCULATION_MISMATCH_PRESENT" in decision.reason_codes


def test_runner_rejects_each_resealed_provenance_binding_and_forged_evaluator() -> None:
    inputs = _inputs()
    changed_inputs = (
        _replace_sealed(
            inputs,
            thresholds=_replace_sealed(
                inputs.thresholds, representative_snapshot_fingerprint=_ref("70")
            ),
        ),
        _replace_sealed(
            inputs,
            source=_replace_sealed(inputs.source, before_manifest_fingerprint=_ref("71")),
        ),
        _replace_sealed(
            inputs,
            gates=_replace_sealed(inputs.gates, outage_oracle_fingerprint=_ref("72")),
        ),
        _replace_sealed(
            inputs,
            gates=_replace_sealed(inputs.gates, disputed_individual_decision_count=1),
        ),
        _replace_sealed(
            inputs,
            operational=_replace_sealed(inputs.operational, observation_fingerprint=_ref("73")),
        ),
        _replace_sealed(
            inputs,
            operational=_replace_sealed(inputs.operational, recall_at_5=replay.Ratio(0, 1)),
        ),
    )
    runner = acceptance_runner.ShadowAcceptanceRunner(acceptance.evaluate_shadow_acceptance)
    for changed in changed_inputs:
        with pytest.raises(acceptance_runner.ShadowAcceptanceRunnerError) as error:
            runner.run(changed)  # type: ignore[arg-type]
        assert error.value.code == "RUNNER_BINDING_INVALID"

    def forged(*_values: object) -> acceptance.ShadowAcceptanceDecision:
        decision = acceptance.evaluate_shadow_acceptance(
            inputs.report,
            inputs.promotion,
            inputs.gates,
            inputs.thresholds,
            inputs.operational,
        )
        object.__setattr__(decision, "replay_fingerprint", None)
        return decision

    with pytest.raises(acceptance_runner.ShadowAcceptanceRunnerError) as error:
        acceptance_runner.ShadowAcceptanceRunner(forged).run(inputs)
    assert error.value.code == "RUNNER_BINDING_INVALID"

    outage_values = {
        "qdrant_unavailable": True,
        "authoritative_decision_delta": 0,
        "oracle_fingerprint": _ref("74"),
        "version": acceptance_runner.SHADOW_ACCEPTANCE_RUNNER_VERSION,
    }
    with pytest.raises(acceptance_runner.ShadowAcceptanceRunnerError) as error:
        _sealed(acceptance_runner.OutageDecisionDelta, outage_values)
    assert error.value.code == "RUNNER_BINDING_INVALID"


def test_runner_returns_unavailable_only_from_controlled_operational_dto() -> None:
    inputs = _inputs()
    values: dict[str, object] = {
        "status": acceptance.OperationalEvidenceStatus.UNAVAILABLE,
        "replay_measurements_fingerprint": None,
        "observation_fingerprint": None,
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
    unavailable = _sealed(acceptance.OperationalEvidence, values)
    changed = _replace_sealed(inputs, operational=unavailable)
    result = acceptance_runner.ShadowAcceptanceRunner(acceptance.evaluate_shadow_acceptance).run(
        changed
    )
    assert result.status is acceptance.ShadowAcceptanceStatus.UNAVAILABLE
