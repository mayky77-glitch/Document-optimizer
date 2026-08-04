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
    PromotionDecision,
    ReplaySnapshotIdentity,
    ReplaySplit,
    replay_fingerprint,
)

SHADOW_ACCEPTANCE_RUNNER_VERSION = "ReconciliationShadowAcceptanceRunner-1.0"
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")


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


@dataclass(frozen=True, slots=True)
class SourceIntegrityEvidence:
    before_fingerprint: str
    after_fingerprint: str
    mutation_count: int
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
        ):
            _error()
        _sealed(self)


@dataclass(frozen=True, slots=True)
class OutageDecisionDelta:
    qdrant_unavailable: bool
    authoritative_decision_delta: int
    fingerprint: str
    version: str = SHADOW_ACCEPTANCE_RUNNER_VERSION

    def __post_init__(self) -> None:
        if (
            self.version != SHADOW_ACCEPTANCE_RUNNER_VERSION
            or not isinstance(self.qdrant_unavailable, bool)
            or not isinstance(self.authoritative_decision_delta, int)
            or isinstance(self.authoritative_decision_delta, bool)
            or self.authoritative_decision_delta < 0
        ):
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
    if not isinstance(inputs, ShadowAcceptanceInputs):
        _error()
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
    if any(not isinstance(value, kind) for value, kind in zip(values, expected, strict=True)):
        _error()
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
        if not isinstance(decision, ShadowAcceptanceDecision):
            _error()
        return decision


def run_shadow_acceptance(
    inputs: ShadowAcceptanceInputs,
    *,
    evaluator: ShadowAcceptanceEvaluator = evaluate_shadow_acceptance,
) -> ShadowAcceptanceDecision:
    """Convenience entry point retaining explicit evaluator injection."""
    return ShadowAcceptanceRunner(evaluator).run(inputs)
