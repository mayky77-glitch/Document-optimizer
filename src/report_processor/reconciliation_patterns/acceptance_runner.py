"""Offline binding coordinator for the Wave 9 shadow-acceptance evaluator.

This module accepts only sealed DTOs and an injected evaluator.  It deliberately
does not discover inputs, access a workbook, or interact with runtime state.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, fields

from .acceptance import (
    HardGateEvidence,
    OperationalEvidence,
    OwnerThresholds,
    ShadowAcceptanceDecision,
    ShadowAcceptanceError,
    evaluate_shadow_acceptance,
)
from .replay import (
    GroupingReplayReport,
    IndexMeasurement,
    PromotionDecision,
    ReplayMeasurements,
    ReplaySnapshotIdentity,
    ReplaySplit,
    SplitReplayMetrics,
    replay_fingerprint,
)

SHADOW_ACCEPTANCE_RUNNER_VERSION = "ReconciliationShadowAcceptanceRunner-1.0"
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_MAX_SIGNED_64 = (1 << 63) - 1
_MAX_LATENCY_SAMPLES = 1_000_000
_MAX_SNAPSHOT_REFS = 10_000


class ShadowAcceptanceRunnerError(ShadowAcceptanceError):
    """Stable fail-closed error for malformed runner bindings."""


def _error() -> None:
    raise ShadowAcceptanceRunnerError("RUNNER_BINDING_INVALID", "runner binding is invalid")


def _sealed(value: object) -> None:
    if not hasattr(value, "fingerprint"):
        _error()
    payload = {
        field.name: getattr(value, field.name)
        for field in fields(value)  # type: ignore[arg-type]
        if field.name != "fingerprint"
    }
    if object.__getattribute__(value, "fingerprint") != replay_fingerprint(payload):
        _error()


def _outage_oracle_fingerprint(value: OutageDecisionDelta) -> str:
    return replay_fingerprint(
        {
            "qdrant_unavailable": value.qdrant_unavailable,
            "authoritative_decision_delta": value.authoritative_decision_delta,
            "version": value.version,
        }
    )


def _operational_observation_fingerprint(
    operational: OperationalEvidence, outage: OutageDecisionDelta
) -> str:
    return replay_fingerprint(
        {
            "status": operational.status,
            "measurements": operational.replay_measurements_fingerprint,
            "recall_at_5": operational.recall_at_5,
            "mrr": operational.mrr,
            "top_1_error": operational.top_1_error,
            "review_rate": operational.review_rate,
            "pattern_reuse_rate": operational.pattern_reuse_rate,
            "operator_correction_rate": operational.operator_correction_rate,
            "suspension_rate": operational.suspension_rate,
            "availability": operational.availability,
            "p95_latency_ns": operational.p95_latency_ns,
            "index_size_bytes": operational.index_size_bytes,
            "outage_oracle": outage.oracle_fingerprint,
        }
    )


@dataclass(frozen=True, slots=True)
class SourceIntegrityEvidence:
    before_fingerprint: str
    after_fingerprint: str
    mutation_count: int
    before_manifest_fingerprint: str
    after_manifest_fingerprint: str
    before_source_set_fingerprint: str
    after_source_set_fingerprint: str
    fingerprint: str
    version: str = SHADOW_ACCEPTANCE_RUNNER_VERSION

    def __post_init__(self) -> None:
        if (
            self.version != SHADOW_ACCEPTANCE_RUNNER_VERSION
            or not isinstance(self.before_fingerprint, str)
            or not isinstance(self.after_fingerprint, str)
            or not _HASH.fullmatch(self.before_fingerprint)
            or not _HASH.fullmatch(self.after_fingerprint)
            or not isinstance(self.mutation_count, int)
            or isinstance(self.mutation_count, bool)
            or self.mutation_count < 0
            or self.mutation_count > _MAX_SIGNED_64
        ):
            _error()
        for value in (
            self.before_manifest_fingerprint,
            self.after_manifest_fingerprint,
            self.before_source_set_fingerprint,
            self.after_source_set_fingerprint,
        ):
            if not isinstance(value, str) or not _HASH.fullmatch(value):
                _error()
        _sealed(self)


@dataclass(frozen=True, slots=True)
class OutageDecisionDelta:
    qdrant_unavailable: bool
    authoritative_decision_delta: int
    oracle_fingerprint: str
    fingerprint: str
    version: str = SHADOW_ACCEPTANCE_RUNNER_VERSION

    def __post_init__(self) -> None:
        if (
            self.version != SHADOW_ACCEPTANCE_RUNNER_VERSION
            or not isinstance(self.qdrant_unavailable, bool)
            or not isinstance(self.authoritative_decision_delta, int)
            or isinstance(self.authoritative_decision_delta, bool)
            or self.authoritative_decision_delta < 0
            or self.authoritative_decision_delta > _MAX_SIGNED_64
            or not isinstance(self.oracle_fingerprint, str)
            or not _HASH.fullmatch(self.oracle_fingerprint)
        ):
            _error()
        if self.oracle_fingerprint != _outage_oracle_fingerprint(self):
            _error()
        _sealed(self)


@dataclass(frozen=True, slots=True)
class ShadowAcceptanceInputs:
    baseline: ReplaySnapshotIdentity
    holdout: ReplaySnapshotIdentity
    report: GroupingReplayReport
    promotion: PromotionDecision
    gates: HardGateEvidence
    thresholds: OwnerThresholds
    operational: OperationalEvidence
    source: SourceIntegrityEvidence
    outage: OutageDecisionDelta
    fingerprint: str
    version: str = SHADOW_ACCEPTANCE_RUNNER_VERSION

    def __post_init__(self) -> None:
        if self.version != SHADOW_ACCEPTANCE_RUNNER_VERSION:
            _error()
        _sealed(self)


ShadowAcceptanceEvaluator = Callable[
    [
        GroupingReplayReport | None,
        PromotionDecision | None,
        HardGateEvidence | None,
        OwnerThresholds | None,
        OperationalEvidence | None,
    ],
    ShadowAcceptanceDecision,
]


def _bind(inputs: ShadowAcceptanceInputs) -> None:
    if type(inputs) is not ShadowAcceptanceInputs:
        _error()
    try:
        values = (
            inputs.baseline,
            inputs.holdout,
            inputs.report,
            inputs.promotion,
            inputs.gates,
            inputs.thresholds,
            inputs.operational,
            inputs.source,
            inputs.outage,
        )
    except (AttributeError, TypeError) as exc:
        raise ShadowAcceptanceRunnerError(
            "RUNNER_BINDING_INVALID", "runner binding is invalid"
        ) from exc
    expected = (
        ReplaySnapshotIdentity,
        ReplaySnapshotIdentity,
        GroupingReplayReport,
        PromotionDecision,
        HardGateEvidence,
        OwnerThresholds,
        OperationalEvidence,
        SourceIntegrityEvidence,
        OutageDecisionDelta,
    )
    if any(type(value) is not kind for value, kind in zip(values, expected, strict=True)):
        _error()
    if (
        type(inputs.report.baseline_metrics) is not SplitReplayMetrics
        or type(inputs.report.holdout_metrics) is not SplitReplayMetrics
        or type(inputs.report.measurements) is not ReplayMeasurements
        or type(inputs.report.measurements.index) is not IndexMeasurement
    ):
        _error()
    if len(inputs.promotion.reason_codes) > 64:
        _error()
    for snapshot in (inputs.baseline, inputs.holdout):
        for count in (snapshot.row_count, snapshot.review_row_count, snapshot.review_group_count):
            if type(count) is not int or not 0 <= count <= _MAX_SIGNED_64:
                _error()
        for refs in (snapshot.source_set_refs, snapshot.document_set_refs):
            if type(refs) is not tuple or len(refs) > _MAX_SNAPSHOT_REFS:
                _error()
    samples = inputs.report.measurements.latency_samples_ns
    if (
        type(samples) is not tuple
        or len(samples) > _MAX_LATENCY_SAMPLES
        or any(type(sample) is not int or not 0 <= sample <= _MAX_SIGNED_64 for sample in samples)
    ):
        _error()
    try:
        inputs.__post_init__()
        _sealed(inputs)
        for value in values:
            value.__post_init__()
            _sealed(value)
    except Exception as exc:
        raise ShadowAcceptanceRunnerError(
            "RUNNER_BINDING_INVALID", "runner binding is invalid"
        ) from exc
    if (
        inputs.baseline.split is not ReplaySplit.BASELINE
        or inputs.holdout.split is not ReplaySplit.HOLDOUT
        or inputs.baseline.fingerprint == inputs.holdout.fingerprint
        or set(inputs.baseline.source_set_refs) & set(inputs.holdout.source_set_refs)
        or set(inputs.baseline.document_set_refs) & set(inputs.holdout.document_set_refs)
        or inputs.baseline.manifest_fingerprint == inputs.holdout.manifest_fingerprint
        or inputs.baseline.corpus_fingerprint == inputs.holdout.corpus_fingerprint
        or (
            inputs.baseline.consequential_version_fingerprint
            != inputs.holdout.consequential_version_fingerprint
        )
    ):
        _error()
    report = inputs.report
    gates = inputs.gates
    if (
        report.baseline_snapshot_fingerprint != inputs.baseline.fingerprint
        or report.holdout_snapshot_fingerprint != inputs.holdout.fingerprint
        or report.baseline_metrics.snapshot_fingerprint != inputs.baseline.fingerprint
        or report.holdout_metrics.snapshot_fingerprint != inputs.holdout.fingerprint
        or gates.replay_fingerprint != report.fingerprint
        or gates.source_before_fingerprint != inputs.source.before_fingerprint
        or gates.source_after_fingerprint != inputs.source.after_fingerprint
        or gates.source_mutation_count != inputs.source.mutation_count
        or gates.qdrant_outage_authoritative_delta != inputs.outage.authoritative_decision_delta
        or inputs.source.before_fingerprint != inputs.source.after_fingerprint
        or inputs.source.mutation_count != 0
        or inputs.outage.authoritative_decision_delta != 0
        or inputs.outage.qdrant_unavailable is not True
        or inputs.thresholds.representative_snapshot_fingerprint != inputs.baseline.fingerprint
        or inputs.thresholds.independent_holdout_snapshot_fingerprint != inputs.holdout.fingerprint
        or inputs.thresholds.representative_corpus_ref != inputs.baseline.corpus_fingerprint
        or inputs.thresholds.independent_holdout_ref != inputs.holdout.corpus_fingerprint
        or inputs.source.before_manifest_fingerprint != inputs.baseline.manifest_fingerprint
        or inputs.source.after_manifest_fingerprint != inputs.holdout.manifest_fingerprint
        or inputs.source.before_source_set_fingerprint
        != replay_fingerprint(inputs.baseline.source_set_refs)
        or inputs.source.after_source_set_fingerprint
        != replay_fingerprint(inputs.holdout.source_set_refs)
        or gates.group_action_observation_fingerprint
        != replay_fingerprint(
            {
                "baseline": report.baseline_metrics.fingerprint,
                "holdout": report.holdout_metrics.fingerprint,
                "current_groups": gates.current_top_level_group_count,
                "repeat_groups": gates.repeat_top_level_group_count,
                "disputed_decisions": gates.disputed_individual_decision_count,
            }
        )
        or gates.outage_oracle_fingerprint != inputs.outage.oracle_fingerprint
        or (
            inputs.operational.status.value == "MEASURED"
            and inputs.operational.observation_fingerprint
            != _operational_observation_fingerprint(inputs.operational, inputs.outage)
        )
    ):
        _error()


@dataclass(frozen=True, slots=True)
class ShadowAcceptanceRunner:
    """Injected, side-effect-free adapter around the frozen core evaluator."""

    evaluator: ShadowAcceptanceEvaluator

    def __post_init__(self) -> None:
        if not callable(self.evaluator):
            _error()

    def run(self, inputs: ShadowAcceptanceInputs) -> ShadowAcceptanceDecision:
        _bind(inputs)
        bound_fingerprint = inputs.fingerprint
        try:
            decision = self.evaluator(
                inputs.report,
                inputs.promotion,
                inputs.gates,
                inputs.thresholds,
                inputs.operational,
            )
        except Exception as exc:
            raise ShadowAcceptanceRunnerError(
                "RUNNER_EVALUATOR_UNAVAILABLE", "runner evaluator is unavailable"
            ) from exc
        _bind(inputs)
        if inputs.fingerprint != bound_fingerprint:
            _error()
        if type(decision) is not ShadowAcceptanceDecision:
            _error()
        try:
            decision.__post_init__()
            _sealed(decision)
        except Exception as exc:
            raise ShadowAcceptanceRunnerError(
                "RUNNER_BINDING_INVALID", "runner binding is invalid"
            ) from exc
        expected = evaluate_shadow_acceptance(
            inputs.report,
            inputs.promotion,
            inputs.gates,
            inputs.thresholds,
            inputs.operational,
        )
        if decision != expected:
            _error()
        return expected


def run_shadow_acceptance(
    inputs: ShadowAcceptanceInputs,
    *,
    evaluator: ShadowAcceptanceEvaluator = evaluate_shadow_acceptance,
) -> ShadowAcceptanceDecision:
    """Convenience entry point retaining explicit evaluator injection."""
    return ShadowAcceptanceRunner(evaluator).run(inputs)
