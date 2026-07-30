"""Small, value-free inputs for the frozen Block 16 audit contract."""

from __future__ import annotations


def run_inputs() -> tuple[tuple[str, ...], dict[str, object], dict[str, str], str]:
    return (
        ("a" * 64, "b" * 64),
        {"count": 2, "boolean_flag": True},
        {"event": "AuditEventEnvelope-16.0", "journal": "StageJournal-16.0"},
        "c" * 64,
    )


def export_rows() -> tuple[dict[str, object], ...]:
    return (
        {"run_id": "run-b", "event_sequence": 2, "count": 7},
        {"run_id": "run-a", "event_sequence": 1, "count": 3},
    )
