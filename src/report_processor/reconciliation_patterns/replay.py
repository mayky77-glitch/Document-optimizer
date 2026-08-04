"""Pure offline Wave 5 replay and promotion gates; no I/O or runtime wiring."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable
from dataclasses import dataclass, fields, is_dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from .offline import CandidateKind, fingerprint
from .pattern_models import ActivationMetadata, PatternRecord, PatternRegistryError, PatternState
from .pattern_registry import RegistryHistory

GROUPING_REPLAY_VERSION = "GroupingReplay-1.0"
GROUPING_PROMOTION_POLICY_VERSION = "GroupingPromotionPolicy-1.0"
ORACLE_RESULT_VERSION = "ReplayOracleResult-1.0"
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_REASON = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")


class ReplaySplit(StrEnum):
    BASELINE = "baseline"
    HOLDOUT = "holdout"


class PromotionVerdict(StrEnum):
    STOP = "stop"
    SHADOW_ELIGIBLE = "shadow_eligible"
    OWNER_APPROVAL_REQUIRED = "owner_approval_required"
    ACTIVATION_ELIGIBLE = "activation_eligible"


class MeasurementStatus(StrEnum):
    MEASURED = "measured"
    NOT_APPLICABLE = "not_applicable"
    UNAVAILABLE = "unavailable"


class GroupingReplayError(PatternRegistryError):
    """Stable privacy-safe Wave 5 contract failure."""


def _error(code: str, message: str = "grouping replay input is invalid") -> None:
    raise GroupingReplayError(code, message)


def _opaque(value: object, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        _error("REPLAY_SCHEMA_INVALID")
    return value


def _count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _error("REPLAY_SCHEMA_INVALID")
    return value


def _refs(value: object, *, minimum: int = 0) -> tuple[str, ...]:
    if (
        not isinstance(value, tuple)
        or len(value) < minimum
        or any(not isinstance(item, str) or not _HASH.fullmatch(item) for item in value)
        or value != tuple(sorted(set(value)))
    ):
        _error("REPLAY_SCHEMA_INVALID")
    return value


def _plain(value: object) -> object:
    if isinstance(value, Decimal):
        return {"decimal": format(value, "f")}
    if isinstance(value, StrEnum):
        return value.value
    if is_dataclass(value):
        return {field.name: _plain(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            _error("REPLAY_SCHEMA_INVALID")
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def replay_fingerprint(value: object) -> str:
    try:
        encoded = json.dumps(
            _plain(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    except (TypeError, ValueError) as exc:
        raise GroupingReplayError(
            "REPLAY_SCHEMA_INVALID", "grouping replay input is invalid"
        ) from exc
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _material(value: object, *, exclude: frozenset[str]) -> dict[str, object]:
    return {
        field.name: getattr(value, field.name)
        for field in fields(value)  # type: ignore[arg-type]
        if field.name not in exclude
    }


def _self_fingerprint(value: object, *, name: str = "fingerprint") -> None:
    actual = getattr(value, name)
    _opaque(actual)
    expected = replay_fingerprint(_material(value, exclude=frozenset({name})))
    if actual != expected:
        _error("REPLAY_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class Ratio:
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        _count(self.numerator)
        _count(self.denominator)
        if self.denominator == 0 and self.numerator != 0:
            _error("REPLAY_SCHEMA_INVALID")
        if self.denominator and self.numerator > self.denominator:
            _error("REPLAY_SCHEMA_INVALID")

    @property
    def undefined(self) -> bool:
        return self.numerator == self.denominator == 0

    def at_least(self, other: Ratio) -> bool:
        if not isinstance(other, Ratio) or self.undefined or other.undefined:
            return False
        return self.numerator * other.denominator >= other.numerator * self.denominator


@dataclass(frozen=True, slots=True)
class OracleResult:
    case_count: int
    mismatch_refs: tuple[str, ...]
    oracle_fingerprint: str
    version: str = ORACLE_RESULT_VERSION

    def __post_init__(self) -> None:
        if self.version != ORACLE_RESULT_VERSION:
            _error("REPLAY_VERSION_UNSUPPORTED")
        if _count(self.case_count) == 0:
            _error("ORACLE_INVALID")
        _refs(self.mismatch_refs)
        if len(self.mismatch_refs) > self.case_count:
            _error("ORACLE_INVALID")
        _self_fingerprint(self, name="oracle_fingerprint")


@dataclass(frozen=True, slots=True)
class ReplaySnapshotIdentity:
    split: ReplaySplit
    snapshot_ref: str
    manifest_fingerprint: str
    corpus_fingerprint: str
    source_set_refs: tuple[str, ...]
    document_set_refs: tuple[str, ...]
    consequential_version_fingerprint: str
    row_count: int
    review_row_count: int
    review_group_count: int
    sealed: bool
    seal_ref: str
    fingerprint: str
    version: str = GROUPING_REPLAY_VERSION

    def __post_init__(self) -> None:
        if self.version != GROUPING_REPLAY_VERSION:
            _error("REPLAY_VERSION_UNSUPPORTED")
        if not isinstance(self.split, ReplaySplit):
            _error("SNAPSHOT_INVALID")
        for value in (
            self.snapshot_ref,
            self.manifest_fingerprint,
            self.corpus_fingerprint,
            self.consequential_version_fingerprint,
            self.seal_ref,
        ):
            _opaque(value)
        _refs(self.source_set_refs, minimum=1)
        _refs(self.document_set_refs, minimum=1)
        for value in (self.row_count, self.review_row_count, self.review_group_count):
            _count(value)
        if self.review_row_count > self.row_count:
            _error("SNAPSHOT_INVALID")
        if self.sealed is not True:
            _error("SNAPSHOT_NOT_SEALED")
        _self_fingerprint(self)


@dataclass(frozen=True, slots=True)
class ReplayObservation:
    snapshot_fingerprint: str
    evaluated_head_fingerprint: str
    effective_decision_fingerprint: str
    pattern_decision_refs: tuple[str, ...]
    correct_decision_refs: tuple[str, ...]
    covered_row_refs: tuple[str, ...]
    covered_group_refs: tuple[str, ...]
    supporting_document_set_refs: tuple[str, ...]
    contradiction_refs: tuple[str, ...]
    forbidden_pair_refs: tuple[str, ...]
    category_change_refs: tuple[str, ...]
    mode_change_refs: tuple[str, ...]
    unit_change_refs: tuple[str, ...]
    decision_mismatch_refs: tuple[str, ...]
    manual_group_count: int
    manual_action_count: int
    unresolved_row_count: int
    double_membership_count: int
    calculation_oracle: OracleResult
    xlsx_oracle: OracleResult
    semantic_fingerprint: str
    version: str = GROUPING_REPLAY_VERSION

    def __post_init__(self) -> None:
        if self.version != GROUPING_REPLAY_VERSION:
            _error("REPLAY_VERSION_UNSUPPORTED")
        for value in (
            self.snapshot_fingerprint,
            self.evaluated_head_fingerprint,
            self.effective_decision_fingerprint,
        ):
            _opaque(value)
        for value in (
            self.pattern_decision_refs,
            self.correct_decision_refs,
            self.covered_row_refs,
            self.covered_group_refs,
            self.supporting_document_set_refs,
            self.contradiction_refs,
            self.forbidden_pair_refs,
            self.category_change_refs,
            self.mode_change_refs,
            self.unit_change_refs,
            self.decision_mismatch_refs,
        ):
            _refs(value)
        if not set(self.correct_decision_refs) <= set(self.pattern_decision_refs):
            _error("REPLAY_SCHEMA_INVALID")
        for value in (
            self.manual_group_count,
            self.manual_action_count,
            self.unresolved_row_count,
            self.double_membership_count,
        ):
            _count(value)
        if not isinstance(self.calculation_oracle, OracleResult) or not isinstance(
            self.xlsx_oracle, OracleResult
        ):
            _error("ORACLE_INVALID")
        _self_fingerprint(self, name="semantic_fingerprint")


@dataclass(frozen=True, slots=True)
class SplitReplayMetrics:
    split: ReplaySplit
    snapshot_fingerprint: str
    coverage_rows: Ratio
    coverage_groups: Ratio
    precision: Ratio
    support_document_set_count: int
    contradiction_count: int
    forbidden_merge_count: int
    manual_group_before: int
    manual_group_after: int
    manual_action_before: int
    manual_action_after: int
    unresolved_before: int
    unresolved_after: int
    changed_category_count: int
    changed_mode_count: int
    changed_unit_count: int
    decision_mismatch_count: int
    double_membership_count: int
    calculation_mismatch_count: int
    xlsx_mismatch_count: int
    before_semantic_fingerprint: str
    after_semantic_fingerprint: str
    repeat_semantic_fingerprint: str
    fingerprint: str
    version: str = GROUPING_REPLAY_VERSION

    def __post_init__(self) -> None:
        if self.version != GROUPING_REPLAY_VERSION or not isinstance(self.split, ReplaySplit):
            _error("REPLAY_VERSION_UNSUPPORTED")
        for value in (
            self.snapshot_fingerprint,
            self.before_semantic_fingerprint,
            self.after_semantic_fingerprint,
            self.repeat_semantic_fingerprint,
        ):
            _opaque(value)
        for value in (
            self.support_document_set_count,
            self.contradiction_count,
            self.forbidden_merge_count,
            self.manual_group_before,
            self.manual_group_after,
            self.manual_action_before,
            self.manual_action_after,
            self.unresolved_before,
            self.unresolved_after,
            self.changed_category_count,
            self.changed_mode_count,
            self.changed_unit_count,
            self.decision_mismatch_count,
            self.double_membership_count,
            self.calculation_mismatch_count,
            self.xlsx_mismatch_count,
        ):
            _count(value)
        if not all(
            isinstance(item, Ratio)
            for item in (self.coverage_rows, self.coverage_groups, self.precision)
        ):
            _error("REPLAY_SCHEMA_INVALID")
        _self_fingerprint(self)


@dataclass(frozen=True, slots=True)
class IndexMeasurement:
    status: MeasurementStatus
    environment_ref: str | None
    index_ref: str | None
    size_bytes: int | None
    fingerprint: str
    version: str = GROUPING_REPLAY_VERSION

    def __post_init__(self) -> None:
        if self.version != GROUPING_REPLAY_VERSION or not isinstance(
            self.status, MeasurementStatus
        ):
            _error("MEASUREMENT_INVALID")
        measured = self.status is MeasurementStatus.MEASURED
        if measured != all(
            item is not None for item in (self.environment_ref, self.index_ref, self.size_bytes)
        ):
            _error("MEASUREMENT_INVALID")
        if not measured and any(
            item is not None for item in (self.environment_ref, self.index_ref, self.size_bytes)
        ):
            _error("MEASUREMENT_INVALID")
        _opaque(self.environment_ref, nullable=True)
        _opaque(self.index_ref, nullable=True)
        if self.size_bytes is not None:
            _count(self.size_bytes)
        _self_fingerprint(self)


@dataclass(frozen=True, slots=True)
class ReplayMeasurements:
    latency_samples_ns: tuple[int, ...]
    p50_latency_ns: int
    p95_latency_ns: int
    index: IndexMeasurement
    fingerprint: str
    version: str = GROUPING_REPLAY_VERSION

    def __post_init__(self) -> None:
        if self.version != GROUPING_REPLAY_VERSION or not self.latency_samples_ns:
            _error("MEASUREMENT_INVALID")
        if any(_count(value) != value for value in self.latency_samples_ns):
            _error("MEASUREMENT_INVALID")
        if self.latency_samples_ns != tuple(sorted(self.latency_samples_ns)):
            _error("MEASUREMENT_INVALID")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in (self.p50_latency_ns, self.p95_latency_ns)
        ):
            _error("MEASUREMENT_INVALID")
        if self.p50_latency_ns != nearest_rank(
            self.latency_samples_ns, 50
        ) or self.p95_latency_ns != nearest_rank(self.latency_samples_ns, 95):
            _error("MEASUREMENT_INVALID")
        if not isinstance(self.index, IndexMeasurement):
            _error("MEASUREMENT_INVALID")
        _self_fingerprint(self)


@dataclass(frozen=True, slots=True)
class PromotionPolicy:
    policy_ref: str
    owner_ref: str
    approval_ref: str
    release_window_ref: str
    allowed_kinds: tuple[CandidateKind, ...]
    allowed_scope_fingerprints: tuple[str, ...]
    min_support_document_sets: int
    min_holdout_document_sets: int
    min_holdout_decisions: int
    min_coverage_rows: Ratio
    min_coverage_groups: Ratio
    min_precision: Ratio
    max_manual_group_count: int
    max_manual_action_count: int
    max_unresolved_row_count: int
    max_p95_latency_ns: int
    index_required: bool
    max_index_size_bytes: int | None
    fingerprint: str
    version: str = GROUPING_PROMOTION_POLICY_VERSION

    def __post_init__(self) -> None:
        if self.version != GROUPING_PROMOTION_POLICY_VERSION:
            _error("REPLAY_VERSION_UNSUPPORTED")
        for value in (self.policy_ref, self.owner_ref, self.approval_ref, self.release_window_ref):
            _opaque(value)
        if (
            not isinstance(self.allowed_kinds, tuple)
            or not self.allowed_kinds
            or any(not isinstance(item, CandidateKind) for item in self.allowed_kinds)
            or self.allowed_kinds
            != tuple(sorted(set(self.allowed_kinds), key=lambda item: item.value))
        ):
            _error("REPLAY_SCHEMA_INVALID")
        _refs(self.allowed_scope_fingerprints, minimum=1)
        for value in (
            self.min_support_document_sets,
            self.min_holdout_document_sets,
            self.min_holdout_decisions,
            self.max_manual_group_count,
            self.max_manual_action_count,
            self.max_unresolved_row_count,
            self.max_p95_latency_ns,
        ):
            _count(value)
        if (
            min(
                self.min_support_document_sets,
                self.min_holdout_document_sets,
                self.min_holdout_decisions,
            )
            < 1
        ):
            _error("REPLAY_SCHEMA_INVALID")
        if not all(
            isinstance(item, Ratio) and not item.undefined
            for item in (self.min_coverage_rows, self.min_coverage_groups, self.min_precision)
        ):
            _error("REPLAY_SCHEMA_INVALID")
        if not isinstance(self.index_required, bool) or self.index_required != (
            self.max_index_size_bytes is not None
        ):
            _error("REPLAY_SCHEMA_INVALID")
        if self.max_index_size_bytes is not None:
            _count(self.max_index_size_bytes)
        _self_fingerprint(self)


@dataclass(frozen=True, slots=True)
class GroupingReplayReport:
    evaluated_pattern_id: str
    evaluated_head_fingerprint: str
    policy_fingerprint: str
    baseline_snapshot_fingerprint: str
    holdout_snapshot_fingerprint: str
    baseline_metrics: SplitReplayMetrics
    holdout_metrics: SplitReplayMetrics
    deterministic_repeatability: bool
    semantic_fingerprint: str
    measurements: ReplayMeasurements
    fingerprint: str
    version: str = GROUPING_REPLAY_VERSION

    def __post_init__(self) -> None:
        if self.version != GROUPING_REPLAY_VERSION:
            _error("REPLAY_VERSION_UNSUPPORTED")
        for value in (
            self.evaluated_pattern_id,
            self.evaluated_head_fingerprint,
            self.policy_fingerprint,
            self.baseline_snapshot_fingerprint,
            self.holdout_snapshot_fingerprint,
        ):
            _opaque(value)
        if not isinstance(self.baseline_metrics, SplitReplayMetrics) or not isinstance(
            self.holdout_metrics, SplitReplayMetrics
        ):
            _error("REPLAY_SCHEMA_INVALID")
        if (
            self.baseline_metrics.split is not ReplaySplit.BASELINE
            or self.holdout_metrics.split is not ReplaySplit.HOLDOUT
            or self.baseline_snapshot_fingerprint == self.holdout_snapshot_fingerprint
            or self.baseline_metrics.snapshot_fingerprint != self.baseline_snapshot_fingerprint
            or self.holdout_metrics.snapshot_fingerprint != self.holdout_snapshot_fingerprint
        ):
            _error("REPLAY_SCHEMA_INVALID")
        if not isinstance(self.deterministic_repeatability, bool) or not isinstance(
            self.measurements, ReplayMeasurements
        ):
            _error("REPLAY_SCHEMA_INVALID")
        repeats = (
            self.baseline_metrics.after_semantic_fingerprint
            == self.baseline_metrics.repeat_semantic_fingerprint
            and self.holdout_metrics.after_semantic_fingerprint
            == self.holdout_metrics.repeat_semantic_fingerprint
        )
        if self.deterministic_repeatability != repeats:
            _error("REPLAY_SCHEMA_INVALID")
        semantic = replay_fingerprint(
            _material(
                self, exclude=frozenset({"semantic_fingerprint", "measurements", "fingerprint"})
            )
        )
        if self.semantic_fingerprint != semantic:
            _error("REPLAY_FINGERPRINT_MISMATCH")
        _self_fingerprint(self)


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    verdict: PromotionVerdict
    reason_codes: tuple[str, ...]
    report_fingerprint: str | None
    policy_fingerprint: str | None
    head_fingerprint: str
    fingerprint: str
    version: str = GROUPING_REPLAY_VERSION

    def __post_init__(self) -> None:
        if self.version != GROUPING_REPLAY_VERSION or not isinstance(
            self.verdict, PromotionVerdict
        ):
            _error("REPLAY_VERSION_UNSUPPORTED")
        if (
            not isinstance(self.reason_codes, tuple)
            or any(
                not isinstance(item, str) or not _REASON.fullmatch(item)
                for item in self.reason_codes
            )
            or self.reason_codes != tuple(sorted(set(self.reason_codes)))
        ):
            _error("REPLAY_SCHEMA_INVALID")
        _opaque(self.report_fingerprint, nullable=True)
        _opaque(self.policy_fingerprint, nullable=True)
        _opaque(self.head_fingerprint)
        if (self.verdict is PromotionVerdict.STOP) != bool(self.reason_codes):
            _error("REPLAY_SCHEMA_INVALID")
        if self.verdict in {
            PromotionVerdict.OWNER_APPROVAL_REQUIRED,
            PromotionVerdict.ACTIVATION_ELIGIBLE,
        } and (self.report_fingerprint is None or self.policy_fingerprint is None):
            _error("REPLAY_SCHEMA_INVALID")
        if self.verdict is PromotionVerdict.SHADOW_ELIGIBLE and (
            self.report_fingerprint is not None or self.policy_fingerprint is not None
        ):
            _error("REPLAY_SCHEMA_INVALID")
        _self_fingerprint(self)


class ReplayExecutor(Protocol):
    def __call__(
        self, pattern: PatternRecord | None, snapshot: ReplaySnapshotIdentity
    ) -> ReplayObservation: ...


class ReplayOracle(Protocol):
    def __call__(
        self, before: ReplayObservation, after: ReplayObservation, snapshot: ReplaySnapshotIdentity
    ) -> OracleResult: ...


def nearest_rank(samples: tuple[int, ...], percentile: int) -> int:
    if (
        not samples
        or isinstance(percentile, bool)
        or not isinstance(percentile, int)
        or not 1 <= percentile <= 100
        or any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in samples)
    ):
        _error("MEASUREMENT_INVALID")
    ordered = tuple(sorted(samples))
    return ordered[math.ceil(percentile * len(ordered) / 100) - 1]


def _decision(
    verdict: PromotionVerdict,
    reasons: tuple[str, ...],
    *,
    head: str,
    report: str | None = None,
    policy: str | None = None,
) -> PromotionDecision:
    values = {
        "verdict": verdict,
        "reason_codes": tuple(sorted(set(reasons))),
        "report_fingerprint": report,
        "policy_fingerprint": policy,
        "head_fingerprint": head,
        "version": GROUPING_REPLAY_VERSION,
    }
    return PromotionDecision(**values, fingerprint=replay_fingerprint(values))


def evaluate_shadow(pattern: PatternRecord) -> PromotionDecision:
    if not isinstance(pattern, PatternRecord):
        _error("REPLAY_SCHEMA_INVALID")
    reasons = []
    if pattern.state not in {PatternState.PROPOSED, PatternState.SHADOW}:
        reasons.append("PATTERN_STATE_INVALID")
    if pattern.support.confirmed_record_count < 3 or pattern.support.document_set_count < 2:
        reasons.append("SUPPORT_INSUFFICIENT")
    if pattern.support.contradictory_atom_count or pattern.contradictions or pattern.risk_codes:
        reasons.append("CONTRADICTION_PRESENT")
    verdict = PromotionVerdict.SHADOW_ELIGIBLE if not reasons else PromotionVerdict.STOP
    return _decision(verdict, tuple(reasons), head=pattern.fingerprint)


def _validate_splits(baseline: ReplaySnapshotIdentity, holdout: ReplaySnapshotIdentity) -> None:
    if baseline.split is not ReplaySplit.BASELINE or holdout.split is not ReplaySplit.HOLDOUT:
        _error("SNAPSHOT_INVALID")
    if (
        set(baseline.source_set_refs) & set(holdout.source_set_refs)
        or set(baseline.document_set_refs) & set(holdout.document_set_refs)
        or baseline.manifest_fingerprint == holdout.manifest_fingerprint
        or baseline.corpus_fingerprint == holdout.corpus_fingerprint
    ):
        _error("SNAPSHOT_OVERLAP")
    if baseline.consequential_version_fingerprint != holdout.consequential_version_fingerprint:
        _error("VERSION_CONTEXT_MISMATCH")


def _bound_observation(
    observation: object, snapshot: ReplaySnapshotIdentity, pattern: PatternRecord
) -> ReplayObservation:
    if not isinstance(observation, ReplayObservation):
        _error("EXECUTOR_INVALID")
    if (
        observation.snapshot_fingerprint != snapshot.fingerprint
        or observation.evaluated_head_fingerprint != pattern.fingerprint
    ):
        _error("EXECUTOR_INVALID")
    if not set(observation.supporting_document_set_refs) <= set(snapshot.document_set_refs):
        _error("EXECUTOR_INVALID")
    if (
        len(observation.covered_row_refs) > snapshot.review_row_count
        or len(observation.covered_group_refs) > snapshot.review_group_count
    ):
        _error("EXECUTOR_INVALID")
    return observation


def _execute(
    executor: ReplayExecutor,
    pattern: PatternRecord | None,
    snapshot: ReplaySnapshotIdentity,
    evaluated: PatternRecord,
) -> ReplayObservation:
    try:
        observation = executor(pattern, snapshot)
    except Exception as exc:
        raise GroupingReplayError("EXECUTOR_INVALID", "replay executor failed") from exc
    return _bound_observation(observation, snapshot, evaluated)


def _run_oracle(
    oracle: ReplayOracle,
    before: ReplayObservation,
    after: ReplayObservation,
    snapshot: ReplaySnapshotIdentity,
) -> OracleResult:
    try:
        result = oracle(before, after, snapshot)
    except Exception as exc:
        raise GroupingReplayError("ORACLE_INVALID", "replay oracle failed") from exc
    if not isinstance(result, OracleResult):
        _error("ORACLE_INVALID")
    return result


def _clock_value(clock: Callable[[], int]) -> int:
    try:
        value = clock()
    except Exception as exc:
        raise GroupingReplayError("MEASUREMENT_INVALID", "replay clock failed") from exc
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _error("MEASUREMENT_INVALID")
    return value


def _metrics(
    split: ReplaySplit,
    snapshot: ReplaySnapshotIdentity,
    before: ReplayObservation,
    after: ReplayObservation,
    repeat: ReplayObservation,
    calculation: OracleResult,
    xlsx: OracleResult,
) -> SplitReplayMetrics:
    if after.semantic_fingerprint != repeat.semantic_fingerprint:
        _error("REPLAY_NONDETERMINISTIC")
    if after.calculation_oracle != calculation or after.xlsx_oracle != xlsx:
        _error("ORACLE_INVALID")
    values = {
        "split": split,
        "snapshot_fingerprint": snapshot.fingerprint,
        "coverage_rows": Ratio(len(after.covered_row_refs), snapshot.review_row_count),
        "coverage_groups": Ratio(len(after.covered_group_refs), snapshot.review_group_count),
        "precision": Ratio(len(after.correct_decision_refs), len(after.pattern_decision_refs)),
        "support_document_set_count": len(after.supporting_document_set_refs),
        "contradiction_count": len(after.contradiction_refs),
        "forbidden_merge_count": len(after.forbidden_pair_refs),
        "manual_group_before": before.manual_group_count,
        "manual_group_after": after.manual_group_count,
        "manual_action_before": before.manual_action_count,
        "manual_action_after": after.manual_action_count,
        "unresolved_before": before.unresolved_row_count,
        "unresolved_after": after.unresolved_row_count,
        "changed_category_count": len(after.category_change_refs),
        "changed_mode_count": len(after.mode_change_refs),
        "changed_unit_count": len(after.unit_change_refs),
        "decision_mismatch_count": len(after.decision_mismatch_refs),
        "double_membership_count": after.double_membership_count,
        "calculation_mismatch_count": len(calculation.mismatch_refs),
        "xlsx_mismatch_count": len(xlsx.mismatch_refs),
        "before_semantic_fingerprint": before.semantic_fingerprint,
        "after_semantic_fingerprint": after.semantic_fingerprint,
        "repeat_semantic_fingerprint": repeat.semantic_fingerprint,
        "version": GROUPING_REPLAY_VERSION,
    }
    return SplitReplayMetrics(**values, fingerprint=replay_fingerprint(values))


def run_grouping_replay(
    pattern: PatternRecord,
    baseline: ReplaySnapshotIdentity,
    holdout: ReplaySnapshotIdentity,
    policy: PromotionPolicy,
    *,
    executor: ReplayExecutor,
    calculation_oracle: ReplayOracle,
    xlsx_oracle: ReplayOracle,
    monotonic_ns: Callable[[], int],
    index_measurement: IndexMeasurement,
) -> GroupingReplayReport:
    if not isinstance(pattern, PatternRecord) or pattern.state is not PatternState.SHADOW:
        _error("PATTERN_STATE_INVALID")
    if not isinstance(policy, PromotionPolicy):
        _error("REPLAY_SCHEMA_INVALID")
    if (
        not isinstance(baseline, ReplaySnapshotIdentity)
        or not isinstance(holdout, ReplaySnapshotIdentity)
        or not isinstance(index_measurement, IndexMeasurement)
        or not callable(executor)
        or not callable(calculation_oracle)
        or not callable(xlsx_oracle)
        or not callable(monotonic_ns)
    ):
        _error("REPLAY_SCHEMA_INVALID")
    _validate_splits(baseline, holdout)
    shadow_decision = evaluate_shadow(pattern)
    if shadow_decision.verdict is not PromotionVerdict.SHADOW_ELIGIBLE:
        _error(shadow_decision.reason_codes[0])
    if pattern.candidate_kind not in policy.allowed_kinds:
        _error("PATTERN_KIND_NOT_ALLOWED")
    if fingerprint(pattern.scope) not in policy.allowed_scope_fingerprints:
        _error("SCOPE_NOT_ALLOWED")
    if pattern.support.document_set_count < policy.min_support_document_sets:
        _error("SUPPORT_INSUFFICIENT")
    if len(holdout.document_set_refs) < policy.min_holdout_document_sets:
        _error("HOLDOUT_INSUFFICIENT")
    metrics = []
    samples = []
    for snapshot in (baseline, holdout):
        before = _execute(executor, None, snapshot, pattern)
        start = _clock_value(monotonic_ns)
        after = _execute(executor, pattern, snapshot, pattern)
        end = _clock_value(monotonic_ns)
        start_repeat = _clock_value(monotonic_ns)
        repeat = _execute(executor, pattern, snapshot, pattern)
        end_repeat = _clock_value(monotonic_ns)
        if end < start or end_repeat < start_repeat:
            _error("MEASUREMENT_INVALID")
        samples.extend((end - start, end_repeat - start_repeat))
        calculation = _run_oracle(calculation_oracle, before, after, snapshot)
        xlsx = _run_oracle(xlsx_oracle, before, after, snapshot)
        metrics.append(_metrics(snapshot.split, snapshot, before, after, repeat, calculation, xlsx))
    ordered_samples = tuple(sorted(samples))
    measurement_values = {
        "latency_samples_ns": ordered_samples,
        "p50_latency_ns": nearest_rank(ordered_samples, 50),
        "p95_latency_ns": nearest_rank(ordered_samples, 95),
        "index": index_measurement,
        "version": GROUPING_REPLAY_VERSION,
    }
    measurements = ReplayMeasurements(
        **measurement_values, fingerprint=replay_fingerprint(measurement_values)
    )
    semantic_values = {
        "evaluated_pattern_id": pattern.pattern_id,
        "evaluated_head_fingerprint": pattern.fingerprint,
        "policy_fingerprint": policy.fingerprint,
        "baseline_snapshot_fingerprint": baseline.fingerprint,
        "holdout_snapshot_fingerprint": holdout.fingerprint,
        "baseline_metrics": metrics[0],
        "holdout_metrics": metrics[1],
        "deterministic_repeatability": True,
        "version": GROUPING_REPLAY_VERSION,
    }
    semantic = replay_fingerprint(semantic_values)
    full_values = {
        **semantic_values,
        "semantic_fingerprint": semantic,
        "measurements": measurements,
    }
    return GroupingReplayReport(**full_values, fingerprint=replay_fingerprint(full_values))


def owner_approval_ref(
    shadow_head: PatternRecord, report: GroupingReplayReport, policy: PromotionPolicy
) -> str:
    if (
        not isinstance(shadow_head, PatternRecord)
        or not isinstance(report, GroupingReplayReport)
        or not isinstance(policy, PromotionPolicy)
        or shadow_head.state is not PatternState.SHADOW
        or report.evaluated_head_fingerprint != shadow_head.fingerprint
        or report.policy_fingerprint != policy.fingerprint
    ):
        _error("OWNER_APPROVAL_STALE")
    return replay_fingerprint(
        {
            "shadow_head": shadow_head.fingerprint,
            "report": report.fingerprint,
            "policy": policy.fingerprint,
        }
    )


derive_owner_approval_ref = owner_approval_ref


_APPROVAL_PRESERVED_FIELDS = (
    "pattern_id",
    "candidate_id",
    "candidate_fingerprint",
    "candidate_kind",
    "versions",
    "scope",
    "template",
    "expected_outcome",
    "support",
    "hard_negative_refs",
    "contradictions",
    "replay",
    "activation",
    "rollback",
    "supersedes_pattern_id",
    "superseded_by_pattern_id",
    "risk_codes",
    "version",
)


def _exact_owner_successor(shadow: PatternRecord, approved: PatternRecord) -> bool:
    return (
        shadow.state is PatternState.SHADOW
        and approved.state is PatternState.OWNER_APPROVED
        and approved.revision == shadow.revision + 1
        and approved.previous_fingerprint == shadow.fingerprint
        and approved.owner is not None
        and approved.owner.approved_revision == approved.revision
        and all(
            getattr(shadow, name) == getattr(approved, name) for name in _APPROVAL_PRESERVED_FIELDS
        )
    )


def evaluate_promotion(
    history: RegistryHistory,
    report: GroupingReplayReport,
    policy: PromotionPolicy | None,
) -> PromotionDecision:
    if (
        not isinstance(history, RegistryHistory)
        or not isinstance(report, GroupingReplayReport)
        or (policy is not None and not isinstance(policy, PromotionPolicy))
    ):
        _error("REPLAY_SCHEMA_INVALID")
    head = history.head
    reasons = []
    if policy is None:
        reasons.append("THRESHOLDS_MISSING")
    if head.state in {PatternState.SUSPENDED, PatternState.RETIRED}:
        reasons.append("REACTIVATION_UNSUPPORTED")
    if head.state is PatternState.SHADOW:
        shadow = head
    elif head.state is PatternState.OWNER_APPROVED and len(history.records) >= 2:
        shadow = history.records[-2]
        if not _exact_owner_successor(shadow, head):
            reasons.append("OWNER_APPROVAL_STALE")
    else:
        shadow = None
        if head.state not in {PatternState.SUSPENDED, PatternState.RETIRED}:
            reasons.append("PATTERN_STATE_INVALID")
    if shadow is None or (
        shadow.pattern_id != report.evaluated_pattern_id
        or shadow.fingerprint != report.evaluated_head_fingerprint
    ):
        reasons.append("OWNER_APPROVAL_STALE")
    if policy is not None:
        if report.policy_fingerprint != policy.fingerprint:
            reasons.append("THRESHOLDS_NOT_APPROVED")
        evaluated = shadow if shadow is not None else head
        if evaluated.support.confirmed_record_count < 3 or evaluated.support.document_set_count < 2:
            reasons.append("SUPPORT_INSUFFICIENT")
        if (
            evaluated.support.contradictory_atom_count
            or evaluated.contradictions
            or evaluated.risk_codes
        ):
            reasons.append("CONTRADICTION_PRESENT")
        if evaluated.candidate_kind not in policy.allowed_kinds:
            reasons.append("PATTERN_KIND_NOT_ALLOWED")
        if fingerprint(evaluated.scope) not in policy.allowed_scope_fingerprints:
            reasons.append("SCOPE_NOT_ALLOWED")
        if evaluated.support.document_set_count < policy.min_support_document_sets:
            reasons.append("SUPPORT_INSUFFICIENT")
        holdout = report.holdout_metrics
        if (
            holdout.support_document_set_count < policy.min_holdout_document_sets
            or holdout.precision.denominator < policy.min_holdout_decisions
        ):
            reasons.append("HOLDOUT_INSUFFICIENT")
        if holdout.precision.undefined:
            reasons.append("PRECISION_UNDEFINED")
        elif not holdout.precision.at_least(policy.min_precision):
            reasons.append("PRECISION_BELOW_THRESHOLD")
        if not holdout.coverage_rows.at_least(
            policy.min_coverage_rows
        ) or not holdout.coverage_groups.at_least(policy.min_coverage_groups):
            reasons.append("COVERAGE_BELOW_THRESHOLD")
        replay_metrics = (report.baseline_metrics, holdout)
        if any(metric.contradiction_count for metric in replay_metrics) or evaluated.contradictions:
            reasons.append("CONTRADICTION_PRESENT")
        if any(metric.forbidden_merge_count for metric in replay_metrics):
            reasons.append("FORBIDDEN_MERGE_PRESENT")
        if any(metric.decision_mismatch_count for metric in replay_metrics):
            reasons.append("DECISION_MISMATCH")
        if any(metric.double_membership_count for metric in replay_metrics):
            reasons.append("DOUBLE_MEMBERSHIP")
        if any(
            metric.manual_group_after > policy.max_manual_group_count
            or metric.manual_action_after > policy.max_manual_action_count
            or metric.unresolved_after > policy.max_unresolved_row_count
            or metric.manual_group_after > metric.manual_group_before
            or metric.manual_action_after > metric.manual_action_before
            or metric.unresolved_after > metric.unresolved_before
            for metric in replay_metrics
        ):
            reasons.append("MANUAL_METRIC_REGRESSION")
        if any(metric.calculation_mismatch_count for metric in replay_metrics):
            reasons.append("CALCULATION_NOT_EQUIVALENT")
        if any(metric.xlsx_mismatch_count for metric in replay_metrics):
            reasons.append("XLSX_NOT_EQUIVALENT")
        if not report.deterministic_repeatability:
            reasons.append("REPLAY_NONDETERMINISTIC")
        if report.measurements.p95_latency_ns > policy.max_p95_latency_ns:
            reasons.append("LATENCY_EXCEEDED")
        index = report.measurements.index
        if policy.index_required:
            if index.status is not MeasurementStatus.MEASURED or index.size_bytes is None:
                reasons.append("INDEX_MEASUREMENT_MISSING")
            elif index.size_bytes > policy.max_index_size_bytes:  # type: ignore[operator]
                reasons.append("INDEX_SIZE_EXCEEDED")
    approval_binding_valid = (
        shadow is not None
        and shadow.pattern_id == report.evaluated_pattern_id
        and shadow.fingerprint == report.evaluated_head_fingerprint
    )
    if (
        head.state is PatternState.OWNER_APPROVED
        and head.owner is not None
        and policy is not None
        and approval_binding_valid
    ):
        expected = owner_approval_ref(shadow, report, policy) if shadow is not None else None
        if head.owner.owner_ref != policy.owner_ref or head.owner.approval_ref != expected:
            reasons.append("OWNER_APPROVAL_STALE")
    if reasons:
        verdict = PromotionVerdict.STOP
    elif head.state is PatternState.SHADOW:
        verdict = PromotionVerdict.OWNER_APPROVAL_REQUIRED
    else:
        verdict = PromotionVerdict.ACTIVATION_ELIGIBLE
    return _decision(
        verdict,
        tuple(reasons),
        head=head.fingerprint,
        report=report.fingerprint,
        policy=policy.fingerprint if policy else None,
    )


def build_activation_metadata(
    history: RegistryHistory,
    report: GroupingReplayReport,
    decision: PromotionDecision,
    policy: PromotionPolicy,
    *,
    activation_ref: str,
) -> ActivationMetadata:
    _opaque(activation_ref)
    if not all(
        (
            isinstance(history, RegistryHistory),
            isinstance(report, GroupingReplayReport),
            isinstance(decision, PromotionDecision),
            isinstance(policy, PromotionPolicy),
        )
    ):
        _error("REPLAY_SCHEMA_INVALID")
    expected_decision = evaluate_promotion(history, report, policy)
    if (
        decision != expected_decision
        or decision.verdict is not PromotionVerdict.ACTIVATION_ELIGIBLE
        or decision.report_fingerprint != report.fingerprint
        or decision.policy_fingerprint != policy.fingerprint
        or decision.head_fingerprint != history.head.fingerprint
        or history.head.state is not PatternState.OWNER_APPROVED
    ):
        _error("PATTERN_STATE_INVALID")
    activation_fingerprint = replay_fingerprint(
        {
            "activation_ref": activation_ref,
            "head": history.head.fingerprint,
            "report": report.fingerprint,
            "policy": policy.fingerprint,
            "owner_approval": history.head.owner.approval_ref if history.head.owner else None,
            "measurements": report.measurements.fingerprint,
        }
    )
    return ActivationMetadata(
        activation_ref,
        activation_fingerprint,
        history.head.revision + 1,
        report.fingerprint,
    )
