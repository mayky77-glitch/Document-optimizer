"""Frozen public contract for the Block 16 audit boundary."""

from dataclasses import fields

from report_processor.audit import (
    AUDIT_BUNDLE_VERSION,
    AUDIT_EVENT_VERSION,
    AUDIT_IDENTITY_VERSION,
    AUDIT_JOURNAL_VERSION,
    FEEDBACK_VERSION,
    RUN_REPORT_VERSION,
    TRACE_REPORT_VERSION,
    AuditBundle,
    AuditErrorCode,
    AuditEvent,
    AuditJournal,
    AuditRun,
    AuditState,
    FeedbackRuleVersion,
    RunReport,
    TraceReport,
    deterministic_bytes,
    export_snapshot,
)


def test_versions_exports_and_controlled_codes_are_frozen() -> None:
    assert (
        AUDIT_IDENTITY_VERSION,
        AUDIT_EVENT_VERSION,
        AUDIT_JOURNAL_VERSION,
        AUDIT_BUNDLE_VERSION,
    ) == ("AuditIdentity-16.0", "AuditEventEnvelope-16.0", "StageJournal-16.0", "AuditBundle-16.0")
    assert (RUN_REPORT_VERSION, TRACE_REPORT_VERSION, FEEDBACK_VERSION) == (
        "RunReport-16.0",
        "TraceReport-16.0",
        "FeedbackRuleVersion-16.0",
    )
    assert tuple(AuditState) == ("PENDING", "DATA_COMMITTED", "EXPORT_PREPARED", "EXPORT_VERIFIED")
    assert tuple(AuditErrorCode) == (
        "HASH_CHAIN_INVALID",
        "SEQUENCE_GAP",
        "INVALID_STAGE_TRANSITION",
        "SNAPSHOT_CHANGED",
        "EXPORT_HASH_MISMATCH",
        "EXPORT_DESTINATION_EXISTS",
        "FEEDBACK_DRIFT",
    )
    assert callable(AuditJournal) and callable(deterministic_bytes) and callable(export_snapshot)


def test_public_result_shapes_are_immutable_and_value_free() -> None:
    assert tuple(field.name for field in fields(AuditRun)) == (
        "run_id",
        "run_key",
        "nonce_hex",
        "input_ref_hashes",
        "options",
        "contract_versions",
        "rule_content_hash",
        "contract_version",
    )
    assert tuple(field.name for field in fields(AuditEvent))[-2:] == ("fields", "contract_version")
    assert tuple(field.name for field in fields(FeedbackRuleVersion))[-2:] == (
        "active",
        "contract_version",
    )
    assert tuple(field.name for field in fields(AuditBundle)) == (
        "run",
        "events",
        "artifact_hashes",
        "contract_version",
    )
    assert tuple(field.name for field in fields(RunReport)) == (
        "run_id",
        "run_key",
        "state",
        "event_count",
        "warning_codes",
        "error_codes",
        "contract_version",
    )
    assert tuple(field.name for field in fields(TraceReport)) == (
        "run_id",
        "links",
        "contract_version",
    )
