"""Immutable, redacted public contracts for the Block 16 audit journal."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

AUDIT_IDENTITY_VERSION = "AuditIdentity-16.0"
AUDIT_EVENT_VERSION = "AuditEventEnvelope-16.0"
AUDIT_JOURNAL_VERSION = "StageJournal-16.0"
AUDIT_BUNDLE_VERSION = "AuditBundle-16.0"
RUN_REPORT_VERSION = "RunReport-16.0"
TRACE_REPORT_VERSION = "TraceReport-16.0"
FEEDBACK_VERSION = "FeedbackRuleVersion-16.0"
GENESIS_EVENT_HASH = "0" * 64


class AuditState(StrEnum):
    PENDING = "PENDING"
    DATA_COMMITTED = "DATA_COMMITTED"
    EXPORT_PREPARED = "EXPORT_PREPARED"
    EXPORT_VERIFIED = "EXPORT_VERIFIED"


class AuditStage(StrEnum):
    RUN = "RUN"
    DATA = "DATA"
    EXPORT = "EXPORT"
    FEEDBACK = "FEEDBACK"
    RECOVERY = "RECOVERY"


class AuditErrorCode(StrEnum):
    HASH_CHAIN_INVALID = "HASH_CHAIN_INVALID"
    SEQUENCE_GAP = "SEQUENCE_GAP"
    INVALID_STAGE_TRANSITION = "INVALID_STAGE_TRANSITION"
    SNAPSHOT_CHANGED = "SNAPSHOT_CHANGED"
    EXPORT_HASH_MISMATCH = "EXPORT_HASH_MISMATCH"
    EXPORT_DESTINATION_EXISTS = "EXPORT_DESTINATION_EXISTS"
    FEEDBACK_DRIFT = "FEEDBACK_DRIFT"


def frozen_mapping(values: Mapping[str, object] | None = None) -> Mapping[str, object]:
    return MappingProxyType(dict(sorted((values or {}).items())))


@dataclass(frozen=True, slots=True)
class AuditRun:
    run_id: str
    run_key: str
    nonce_hex: str
    input_ref_hashes: tuple[str, ...]
    options: Mapping[str, object] = field(default_factory=frozen_mapping)
    contract_versions: Mapping[str, str] = field(default_factory=frozen_mapping)
    rule_content_hash: str = ""
    contract_version: str = field(default=AUDIT_IDENTITY_VERSION, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_ref_hashes", tuple(sorted(set(self.input_ref_hashes))))
        object.__setattr__(self, "options", frozen_mapping(self.options))
        object.__setattr__(self, "contract_versions", frozen_mapping(self.contract_versions))


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_id: str
    run_id: str
    event_sequence: int
    stage_attempt_id: str
    controlled_stage_code: str
    controlled_state_code: str
    controlled_reason_code: str | None
    controlled_warning_code: str | None
    previous_event_hash: str
    event_hash: str
    timestamp_utc: str
    fields: Mapping[str, object] = field(default_factory=frozen_mapping)
    contract_version: str = field(default=AUDIT_EVENT_VERSION, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", frozen_mapping(self.fields))


@dataclass(frozen=True, slots=True)
class FeedbackRuleVersion:
    rule_version_id: str
    run_id: str
    source_event_id: str
    rule_content_hash: str
    source_hash: str
    active: bool = False
    contract_version: str = field(default=FEEDBACK_VERSION, init=False)


@dataclass(frozen=True, slots=True)
class AuditBundle:
    run: AuditRun
    events: tuple[AuditEvent, ...]
    artifact_hashes: Mapping[str, str]
    contract_version: str = field(default=AUDIT_BUNDLE_VERSION, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "events", tuple(self.events))
        object.__setattr__(self, "artifact_hashes", frozen_mapping(self.artifact_hashes))


@dataclass(frozen=True, slots=True)
class RunReport:
    run_id: str
    run_key: str
    state: str
    event_count: int
    warning_codes: tuple[str, ...]
    error_codes: tuple[str, ...]
    contract_version: str = field(default=RUN_REPORT_VERSION, init=False)


@dataclass(frozen=True, slots=True)
class TraceReport:
    run_id: str
    links: tuple[Mapping[str, object], ...]
    contract_version: str = field(default=TRACE_REPORT_VERSION, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "links", tuple(frozen_mapping(link) for link in self.links))
