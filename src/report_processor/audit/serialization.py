"""Canonical serialization and strict redaction used by every audit boundary."""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping
from enum import Enum
from hashlib import sha256
from typing import Any

from .models import AuditEvent

EXPORT_ALLOWLIST = frozenset(
    {
        "contract_version",
        "run_id",
        "run_key",
        "stage_attempt_id",
        "event_id",
        "event_sequence",
        "previous_event_hash",
        "event_hash",
        "controlled_stage_code",
        "controlled_state_code",
        "controlled_reason_code",
        "controlled_warning_code",
        "artifact_id",
        "artifact_sha256",
        "input_ref_hash",
        "output_ref_hash",
        "rule_version_id",
        "source_row_id",
        "line_id",
        "target_row_id",
        "candidate_id",
        "match_result_id",
        "calculation_id",
        "trace_id",
        "write_id",
        "row_number",
        "column_number",
        "coordinate",
        "hashed_sheet_ref",
        "count",
        "boolean_flag",
        "timestamp_utc",
    }
)


class AuditRedactionError(ValueError):
    """Raised when unapproved data would cross the audit boundary."""


def canonical(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): canonical(item) for key, item in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [canonical(item) for item in value]
    if dataclasses.is_dataclass(value):
        return {
            field.name: canonical(getattr(value, field.name)) for field in dataclasses.fields(value)
        }
    raise TypeError(f"unsupported canonical audit value: {type(value).__name__}")


def canonical_json(value: object) -> str:
    return json.dumps(canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: object) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def redact(fields: Mapping[str, object]) -> dict[str, object]:
    unknown = set(fields).difference(EXPORT_ALLOWLIST)
    if unknown:
        raise AuditRedactionError(f"non-allowlisted audit fields: {sorted(unknown)!r}")
    result = canonical(fields)
    if not isinstance(result, dict):
        raise AuditRedactionError("audit fields must be a mapping")
    for key, value in result.items():
        if isinstance(value, (dict, list)):
            raise AuditRedactionError(f"nested audit field is not allowed: {key}")
    return result


def event_payload(event: AuditEvent) -> dict[str, object]:
    fields = redact(event.fields)
    return {
        "contract_version": event.contract_version,
        "run_id": event.run_id,
        "event_id": event.event_id,
        "event_sequence": event.event_sequence,
        "stage_attempt_id": event.stage_attempt_id,
        "controlled_stage_code": event.controlled_stage_code,
        "controlled_state_code": event.controlled_state_code,
        "controlled_reason_code": event.controlled_reason_code,
        "controlled_warning_code": event.controlled_warning_code,
        "previous_event_hash": event.previous_event_hash,
        "event_hash": event.event_hash,
        "timestamp_utc": event.timestamp_utc,
        **fields,
    }
