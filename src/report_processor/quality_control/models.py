"""Immutable, privacy-safe public contract for Block 14 quality control."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

QUALITY_CONTROL_CONTRACT_VERSION = "QualityControlContract-14.0"
QUALITY_CONTROL_ENGINE_VERSION = "QualityControlEngine-14.0"


class QualityDecision(StrEnum):
    ALLOW_WRITE = "allow_write"
    ALLOW_WRITE_WITH_WARNINGS = "allow_write_with_warnings"
    REQUIRE_MANUAL_REVIEW = "require_manual_review"
    BLOCK_WRITE = "block_write"


class QualitySeverity(StrEnum):
    WARNING = "warning"
    MANUAL_REVIEW = "manual_review"
    BLOCKING = "blocking"


def _freeze_safe_mapping(values: Mapping[str, object]) -> Mapping[str, object]:
    copied = dict(values)
    if any(not isinstance(key, str) for key in copied):
        raise TypeError("evidence keys должны быть строками")
    return MappingProxyType(dict(sorted(copied.items())))


@dataclass(frozen=True, slots=True)
class QualityLocation:
    source_kind: str
    source_id: str
    sheet_name: str | None = None
    row_number: int | None = None
    coordinate: str | None = None


@dataclass(frozen=True, slots=True)
class QualityIssue:
    issue_id: str
    code: str
    severity: QualitySeverity
    message: str
    target_row_id: str | None
    match_result_id: str | None
    calculation_id: str | None
    source_row_ids: tuple[str, ...]
    locations: tuple[QualityLocation, ...]
    evidence: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_row_ids", tuple(sorted(set(self.source_row_ids))))
        object.__setattr__(self, "locations", tuple(self.locations))
        if any(not isinstance(item, QualityLocation) for item in self.locations):
            raise TypeError("locations должен содержать QualityLocation")
        object.__setattr__(self, "evidence", _freeze_safe_mapping(self.evidence))


@dataclass(frozen=True, slots=True)
class QualityControlSummary:
    match_count: int
    calculation_count: int
    matched_count: int
    ambiguous_count: int
    unmatched_count: int
    calculated_count: int
    warning_issue_count: int
    manual_review_issue_count: int
    blocking_issue_count: int


@dataclass(frozen=True, slots=True)
class QualityControlReport:
    report_id: str
    input_digest: str
    rule_set_hash: str
    decision: QualityDecision
    issues: tuple[QualityIssue, ...]
    summary: QualityControlSummary
    match_result_ids: tuple[str, ...]
    calculation_ids: tuple[str, ...]
    contract_version: str = field(init=False, default=QUALITY_CONTROL_CONTRACT_VERSION)

    def __post_init__(self) -> None:
        if not isinstance(self.issues, tuple) or any(
            not isinstance(item, QualityIssue) for item in self.issues
        ):
            raise TypeError("issues должен быть tuple QualityIssue")
        object.__setattr__(self, "match_result_ids", tuple(sorted(self.match_result_ids)))
        object.__setattr__(self, "calculation_ids", tuple(sorted(self.calculation_ids)))
