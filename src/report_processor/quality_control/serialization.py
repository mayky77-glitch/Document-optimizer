"""Canonical identities and privacy-safe report assembly helpers."""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterable, Mapping
from decimal import Decimal
from enum import Enum
from hashlib import sha256
from typing import Any

from report_processor.calculation import CalculationResult, CalculationStatus
from report_processor.matching import MatchResult, MatchStatus

from .exceptions import QualityControlInputError
from .models import (
    QUALITY_CONTROL_CONTRACT_VERSION,
    QualityControlSummary,
    QualityDecision,
    QualityIssue,
    QualityLocation,
    QualitySeverity,
)

_SENSITIVE_FIELDS = frozenset(
    {
        "raw_value",
        "raw_lexeme",
        "formula",
        "raw_formula_lexeme",
        "raw_cached_lexeme",
        "cached_value",
        "comment_text",
    }
)
_SEVERITY_ORDER = {
    QualitySeverity.BLOCKING: 0,
    QualitySeverity.MANUAL_REVIEW: 1,
    QualitySeverity.WARNING: 2,
}


def finite_decimal(value: object, field_name: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise QualityControlInputError(
            "INVALID_DECIMAL", f"{field_name} должен быть конечным Decimal"
        )
    return value


def issue(
    issues: list[QualityIssue],
    code: str,
    severity: str,
    message: str,
    *,
    match: MatchResult | None = None,
    calculation: CalculationResult | None = None,
    source_row_ids: tuple[str, ...] = (),
    evidence: Mapping[str, object] | None = None,
) -> None:
    quality_severity = QualitySeverity(severity)
    target_row_id = (
        match.target_row_id if match else (calculation.target_row_id if calculation else None)
    )
    match_result_id = (
        match.result_id if match else (calculation.match_result_id if calculation else None)
    )
    calculation_id = calculation.calculation_id if calculation else None
    locations = _locations(match, calculation)
    safe_evidence = dict(evidence or {})
    issue_id = _hash(
        QUALITY_CONTROL_CONTRACT_VERSION,
        code,
        target_row_id,
        match_result_id,
        calculation_id,
        tuple(sorted(source_row_ids)),
        tuple(_location_data(item) for item in locations),
        canonical(safe_evidence),
    )
    issues.append(
        QualityIssue(
            issue_id,
            code,
            quality_severity,
            message,
            target_row_id,
            match_result_id,
            calculation_id,
            source_row_ids,
            locations,
            safe_evidence,
        )
    )


def decision(issues: tuple[QualityIssue, ...]) -> QualityDecision:
    for severity, result in (
        (QualitySeverity.BLOCKING, QualityDecision.BLOCK_WRITE),
        (QualitySeverity.MANUAL_REVIEW, QualityDecision.REQUIRE_MANUAL_REVIEW),
        (QualitySeverity.WARNING, QualityDecision.ALLOW_WRITE_WITH_WARNINGS),
    ):
        if any(item.severity is severity for item in issues):
            return result
    return QualityDecision.ALLOW_WRITE


def summary(
    matches: tuple[MatchResult, ...],
    calculations: tuple[CalculationResult, ...],
    issues: tuple[QualityIssue, ...],
) -> QualityControlSummary:
    return QualityControlSummary(
        len(matches),
        len(calculations),
        sum(x.status is MatchStatus.MATCHED for x in matches),
        sum(x.status is MatchStatus.AMBIGUOUS for x in matches),
        sum(x.status is MatchStatus.UNMATCHED for x in matches),
        sum(
            x.status in {CalculationStatus.CALCULATED, CalculationStatus.CALCULATED_WITH_WARNINGS}
            for x in calculations
        ),
        sum(x.severity is QualitySeverity.WARNING for x in issues),
        sum(x.severity is QualitySeverity.MANUAL_REVIEW for x in issues),
        sum(x.severity is QualitySeverity.BLOCKING for x in issues),
    )


def digest(matches: Iterable[object], calculations: Iterable[object], rule_set: object) -> str:
    rule_hash = getattr(rule_set, "content_hash", "")
    payload = {
        "contract": QUALITY_CONTROL_CONTRACT_VERSION,
        "matches": sorted((canonical(item) for item in matches), key=canonical_json),
        "calculations": sorted((canonical(item) for item in calculations), key=canonical_json),
        "rule_set_hash": rule_hash,
    }
    return sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def report_identity(
    input_digest: str,
    result_decision: QualityDecision,
    issue_ids: tuple[str, ...],
) -> str:
    return _hash(
        QUALITY_CONTROL_CONTRACT_VERSION,
        input_digest,
        result_decision.value,
        issue_ids,
    )


def issue_sort_key(issue_value: QualityIssue) -> tuple[object, ...]:
    return (
        _SEVERITY_ORDER[issue_value.severity],
        issue_value.code,
        issue_value.target_row_id or "",
        issue_value.match_result_id or "",
        issue_value.calculation_id or "",
        issue_value.issue_id,
    )


def sum_optional(values: Iterable[Decimal | None]) -> Decimal | None:
    present = tuple(value for value in values if value is not None)
    return sum(present, Decimal("0")) if present else None


def canonical(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(finite_decimal(value, "input"), "f")
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {
            str(key): canonical(item)
            for key, item in sorted(value.items())
            if str(key) not in _SENSITIVE_FIELDS
        }
    if isinstance(value, (tuple, list)):
        return [canonical(item) for item in value]
    if dataclasses.is_dataclass(value):
        return {
            field.name: canonical(getattr(value, field.name))
            for field in dataclasses.fields(value)
            if field.name not in _SENSITIVE_FIELDS
        }
    return str(value)


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(*parts: object) -> str:
    return sha256(canonical_json(canonical(parts)).encode("utf-8")).hexdigest()


def _locations(
    match: MatchResult | None, calculation: CalculationResult | None
) -> tuple[QualityLocation, ...]:
    target = match.target_row if match else (calculation.target_row if calculation else None)
    if target is None:
        return ()
    return (
        QualityLocation(
            "target",
            getattr(target, "sheet_name", ""),
            getattr(target, "sheet_name", None),
            getattr(target, "row_number", None),
        ),
    )


def _location_data(location: QualityLocation) -> tuple[object, ...]:
    return (
        location.source_kind,
        location.source_id,
        location.sheet_name,
        location.row_number,
        location.coordinate,
    )
