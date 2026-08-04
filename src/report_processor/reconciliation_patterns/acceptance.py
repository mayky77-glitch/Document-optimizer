"""Pure, fail-closed Wave 9 shadow-acceptance aggregate contract."""

from __future__ import annotations

import re
from dataclasses import dataclass, fields
from enum import StrEnum

from .replay import (
    GroupingReplayError,
    GroupingReplayReport,
    MeasurementStatus,
    PromotionDecision,
    PromotionVerdict,
    Ratio,
    replay_fingerprint,
)

RECONCILIATION_SHADOW_ACCEPTANCE_VERSION = "ReconciliationShadowAcceptance-1.0"
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")


class ShadowAcceptanceStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    UNAVAILABLE = "UNAVAILABLE"


class OperationalEvidenceStatus(StrEnum):
    MEASURED = "MEASURED"
    UNAVAILABLE = "UNAVAILABLE"


class ShadowAcceptanceError(GroupingReplayError):
    """Stable privacy-safe shadow-acceptance contract failure."""


def _error(code: str) -> None:
    raise ShadowAcceptanceError(code, "shadow acceptance input is invalid")


def _opaque(value: object) -> str:
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        _error("ACCEPTANCE_SCHEMA_INVALID")
    return value


def _count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _error("ACCEPTANCE_SCHEMA_INVALID")
    return value


def _ratio(value: object, *, defined: bool = True) -> Ratio:
    if not isinstance(value, Ratio) or (defined and value.undefined):
        _error("ACCEPTANCE_SCHEMA_INVALID")
    return value


def _fingerprint(value: object) -> str:
    values = {
        field.name: getattr(value, field.name)
        for field in fields(value)
        if field.name != "fingerprint"
    }
    return replay_fingerprint(values)


def _sealed(value: object) -> None:
    _opaque(getattr(value, "fingerprint", None))
    if value.fingerprint != _fingerprint(value):
        _error("ACCEPTANCE_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class OwnerThresholds:
    threshold_ref: str
    owner_ref: str
    representative_corpus_ref: str
    independent_holdout_ref: str
    min_recall_at_5: Ratio
    min_mrr: Ratio
    max_top_1_error: Ratio
    max_review_rate: Ratio
    min_pattern_reuse_rate: Ratio
    max_operator_correction_rate: Ratio
    max_suspension_rate: Ratio
    min_availability: Ratio
    max_p95_latency_ns: int
    max_index_size_bytes: int
    fingerprint: str
    version: str = RECONCILIATION_SHADOW_ACCEPTANCE_VERSION

    def __post_init__(self) -> None:
        if self.version != RECONCILIATION_SHADOW_ACCEPTANCE_VERSION:
            _error("ACCEPTANCE_VERSION_UNSUPPORTED")
        for value in (
            self.threshold_ref,
            self.owner_ref,
            self.representative_corpus_ref,
            self.independent_holdout_ref,
        ):
            _opaque(value)
        for value in (
            self.min_recall_at_5,
            self.min_mrr,
            self.max_top_1_error,
            self.max_review_rate,
            self.min_pattern_reuse_rate,
            self.max_operator_correction_rate,
            self.max_suspension_rate,
            self.min_availability,
        ):
            _ratio(value)
        _count(self.max_p95_latency_ns)
        _count(self.max_index_size_bytes)
        _sealed(self)


@dataclass(frozen=True, slots=True)
class OperationalEvidence:
    status: OperationalEvidenceStatus
    replay_measurements_fingerprint: str | None
    recall_at_5: Ratio | None
    mrr: Ratio | None
    top_1_error: Ratio | None
    review_rate: Ratio | None
    pattern_reuse_rate: Ratio | None
    operator_correction_rate: Ratio | None
    suspension_rate: Ratio | None
    availability: Ratio | None
    p95_latency_ns: int | None
    index_size_bytes: int | None
    fingerprint: str
    version: str = RECONCILIATION_SHADOW_ACCEPTANCE_VERSION

    def __post_init__(self) -> None:
        if self.version != RECONCILIATION_SHADOW_ACCEPTANCE_VERSION or not isinstance(
            self.status, OperationalEvidenceStatus
        ):
            _error("ACCEPTANCE_SCHEMA_INVALID")
        values = (
            self.replay_measurements_fingerprint,
            self.recall_at_5,
            self.mrr,
            self.top_1_error,
            self.review_rate,
            self.pattern_reuse_rate,
            self.operator_correction_rate,
            self.suspension_rate,
            self.availability,
            self.p95_latency_ns,
            self.index_size_bytes,
        )
        if self.status is OperationalEvidenceStatus.UNAVAILABLE:
            if any(value is not None for value in values):
                _error("ACCEPTANCE_SCHEMA_INVALID")
        else:
            if any(value is None for value in values):
                _error("ACCEPTANCE_SCHEMA_INVALID")
            _opaque(self.replay_measurements_fingerprint)
            for value in values[1:9]:
                _ratio(value)
            _count(self.p95_latency_ns)
            _count(self.index_size_bytes)
        _sealed(self)


@dataclass(frozen=True, slots=True)
class HardGateEvidence:
    replay_fingerprint: str
    source_before_fingerprint: str
    source_after_fingerprint: str
    current_top_level_group_count: int
    repeat_top_level_group_count: int
    disputed_individual_decision_count: int
    forbidden_merge_count: int
    double_membership_count: int
    relevant_nonzero_row_coverage: Ratio
    calculation_mismatch_count: int
    xlsx_mismatch_count: int
    qdrant_outage_authoritative_delta: int
    source_mutation_count: int
    deterministic_repeatability: bool
    fingerprint: str
    version: str = RECONCILIATION_SHADOW_ACCEPTANCE_VERSION

    def __post_init__(self) -> None:
        if self.version != RECONCILIATION_SHADOW_ACCEPTANCE_VERSION:
            _error("ACCEPTANCE_VERSION_UNSUPPORTED")
        for value in (
            self.replay_fingerprint,
            self.source_before_fingerprint,
            self.source_after_fingerprint,
        ):
            _opaque(value)
        for value in (
            self.current_top_level_group_count,
            self.repeat_top_level_group_count,
            self.disputed_individual_decision_count,
            self.forbidden_merge_count,
            self.double_membership_count,
            self.calculation_mismatch_count,
            self.xlsx_mismatch_count,
            self.qdrant_outage_authoritative_delta,
            self.source_mutation_count,
        ):
            _count(value)
        _ratio(self.relevant_nonzero_row_coverage)
        if not isinstance(self.deterministic_repeatability, bool):
            _error("ACCEPTANCE_SCHEMA_INVALID")
        _sealed(self)


@dataclass(frozen=True, slots=True)
class ShadowAcceptanceDecision:
    status: ShadowAcceptanceStatus
    reason_codes: tuple[str, ...]
    replay_fingerprint: str | None
    promotion_fingerprint: str | None
    hard_gate_fingerprint: str | None
    threshold_fingerprint: str | None
    operational_fingerprint: str | None
    fingerprint: str
    version: str = RECONCILIATION_SHADOW_ACCEPTANCE_VERSION

    def __post_init__(self) -> None:
        if self.version != RECONCILIATION_SHADOW_ACCEPTANCE_VERSION or not isinstance(
            self.status, ShadowAcceptanceStatus
        ):
            _error("ACCEPTANCE_SCHEMA_INVALID")
        if (
            not isinstance(self.reason_codes, tuple)
            or any(
                not isinstance(code, str) or not _CODE.fullmatch(code) for code in self.reason_codes
            )
            or self.reason_codes != tuple(sorted(set(self.reason_codes)))
        ):
            _error("ACCEPTANCE_SCHEMA_INVALID")
        for value in (
            self.replay_fingerprint,
            self.promotion_fingerprint,
            self.hard_gate_fingerprint,
            self.threshold_fingerprint,
            self.operational_fingerprint,
        ):
            if value is not None:
                _opaque(value)
        if self.status is ShadowAcceptanceStatus.PASS and self.reason_codes:
            _error("ACCEPTANCE_SCHEMA_INVALID")
        if self.status is not ShadowAcceptanceStatus.PASS and not self.reason_codes:
            _error("ACCEPTANCE_SCHEMA_INVALID")
        _sealed(self)


def _decision(
    status: ShadowAcceptanceStatus,
    reasons: tuple[str, ...],
    report: GroupingReplayReport | None,
    promotion: PromotionDecision | None,
    gates: HardGateEvidence | None,
    thresholds: OwnerThresholds | None,
    operational: OperationalEvidence | None,
) -> ShadowAcceptanceDecision:
    values = {
        "status": status,
        "reason_codes": tuple(sorted(set(reasons))),
        "replay_fingerprint": report.fingerprint if report else None,
        "promotion_fingerprint": promotion.fingerprint if promotion else None,
        "hard_gate_fingerprint": gates.fingerprint if gates else None,
        "threshold_fingerprint": thresholds.fingerprint if thresholds else None,
        "operational_fingerprint": operational.fingerprint if operational else None,
        "version": RECONCILIATION_SHADOW_ACCEPTANCE_VERSION,
    }
    return ShadowAcceptanceDecision(**values, fingerprint=replay_fingerprint(values))


def evaluate_shadow_acceptance(
    report: GroupingReplayReport | None,
    promotion: PromotionDecision | None,
    gates: HardGateEvidence | None,
    thresholds: OwnerThresholds | None,
    operational: OperationalEvidence | None,
) -> ShadowAcceptanceDecision:
    """Evaluate only supplied aggregate evidence; never activate or mutate state."""
    supplied = (report, promotion, gates, thresholds, operational)
    expected = (
        GroupingReplayReport,
        PromotionDecision,
        HardGateEvidence,
        OwnerThresholds,
        OperationalEvidence,
    )
    if any(
        value is not None and not isinstance(value, kind)
        for value, kind in zip(supplied, expected, strict=True)
    ):
        _error("ACCEPTANCE_SCHEMA_INVALID")
    missing = []
    if report is None:
        missing.append("REPLAY_REPORT_MISSING")
    if promotion is None:
        missing.append("PROMOTION_DECISION_MISSING")
    if gates is None:
        missing.append("HARD_GATE_EVIDENCE_MISSING")
    if thresholds is None:
        missing.append("OWNER_THRESHOLDS_MISSING")
    if operational is None:
        missing.append("OPERATIONAL_MEASUREMENTS_MISSING")
    if missing:
        return _decision(
            ShadowAcceptanceStatus.BLOCKED,
            tuple(missing),
            report,
            promotion,
            gates,
            thresholds,
            operational,
        )
    assert (
        report is not None
        and promotion is not None
        and gates is not None
        and thresholds is not None
        and operational is not None
    )
    if operational.status is OperationalEvidenceStatus.UNAVAILABLE:
        return _decision(
            ShadowAcceptanceStatus.UNAVAILABLE,
            ("DEPENDENCY_UNAVAILABLE",),
            report,
            promotion,
            gates,
            thresholds,
            operational,
        )
    reasons = []
    if (
        promotion.report_fingerprint != report.fingerprint
        or promotion.policy_fingerprint != report.policy_fingerprint
        or promotion.head_fingerprint != report.evaluated_head_fingerprint
    ):
        reasons.append("PROMOTION_BINDING_INVALID")
    if promotion.verdict is PromotionVerdict.STOP:
        reasons.append("PROMOTION_STOP")
    if gates.replay_fingerprint != report.fingerprint:
        reasons.append("HARD_GATE_BINDING_INVALID")
    if (
        gates.source_before_fingerprint != gates.source_after_fingerprint
        or gates.source_mutation_count
    ):
        reasons.append("SOURCE_MUTATION_PRESENT")
    if gates.current_top_level_group_count > 50:
        reasons.append("CURRENT_GROUP_LIMIT_EXCEEDED")
    if gates.repeat_top_level_group_count > 30:
        reasons.append("REPEAT_GROUP_LIMIT_EXCEEDED")
    if gates.disputed_individual_decision_count > 20:
        reasons.append("DISPUTED_DECISION_LIMIT_EXCEEDED")
    if gates.forbidden_merge_count:
        reasons.append("FORBIDDEN_MERGE_PRESENT")
    if gates.double_membership_count:
        reasons.append("DOUBLE_MEMBERSHIP_PRESENT")
    if gates.relevant_nonzero_row_coverage != Ratio(1, 1):
        reasons.append("ROW_COVERAGE_INCOMPLETE")
    if gates.calculation_mismatch_count:
        reasons.append("CALCULATION_MISMATCH_PRESENT")
    if gates.xlsx_mismatch_count:
        reasons.append("XLSX_MISMATCH_PRESENT")
    if gates.qdrant_outage_authoritative_delta:
        reasons.append("OUTAGE_DELTA_PRESENT")
    if not gates.deterministic_repeatability or not report.deterministic_repeatability:
        reasons.append("REPEATABILITY_FAILED")
    if operational.replay_measurements_fingerprint != report.measurements.fingerprint:
        reasons.append("OPERATIONAL_BINDING_INVALID")
    if operational.p95_latency_ns != report.measurements.p95_latency_ns:
        reasons.append("LATENCY_BINDING_INVALID")
    index = report.measurements.index
    if (
        index.status is not MeasurementStatus.MEASURED
        or operational.index_size_bytes != index.size_bytes
    ):
        reasons.append("INDEX_BINDING_INVALID")
    checks = (
        (
            operational.recall_at_5.at_least(thresholds.min_recall_at_5),
            "RECALL_AT_5_BELOW_THRESHOLD",
        ),
        (operational.mrr.at_least(thresholds.min_mrr), "MRR_BELOW_THRESHOLD"),
        (thresholds.max_top_1_error.at_least(operational.top_1_error), "TOP_1_ERROR_EXCEEDED"),
        (thresholds.max_review_rate.at_least(operational.review_rate), "REVIEW_RATE_EXCEEDED"),
        (
            operational.pattern_reuse_rate.at_least(thresholds.min_pattern_reuse_rate),
            "REUSE_RATE_BELOW_THRESHOLD",
        ),
        (
            thresholds.max_operator_correction_rate.at_least(operational.operator_correction_rate),
            "CORRECTION_RATE_EXCEEDED",
        ),
        (
            thresholds.max_suspension_rate.at_least(operational.suspension_rate),
            "SUSPENSION_RATE_EXCEEDED",
        ),
        (
            operational.availability.at_least(thresholds.min_availability),
            "AVAILABILITY_BELOW_THRESHOLD",
        ),
        (operational.p95_latency_ns <= thresholds.max_p95_latency_ns, "LATENCY_EXCEEDED"),
        (operational.index_size_bytes <= thresholds.max_index_size_bytes, "INDEX_SIZE_EXCEEDED"),
    )
    reasons.extend(code for passed, code in checks if not passed)
    status = ShadowAcceptanceStatus.FAIL if reasons else ShadowAcceptanceStatus.PASS
    return _decision(status, tuple(reasons), report, promotion, gates, thresholds, operational)
