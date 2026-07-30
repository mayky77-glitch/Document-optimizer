from __future__ import annotations

import pytest

from report_processor.audit import (
    AuditJournal,
    AuditRedactionError,
    canonical_json,
    redact,
    trace_report,
)


def test_canonical_json_is_sorted_utf8_safe_and_allowlist_is_strict() -> None:
    assert canonical_json({"count": 1, "run_id": "ид"}) == '{"count":1,"run_id":"ид"}'
    assert redact({"run_id": "r", "count": 1}) == {"count": 1, "run_id": "r"}
    with pytest.raises(AuditRedactionError):
        redact({"formula": "=A1"})


def test_nested_values_are_rejected_at_the_audit_boundary() -> None:
    with pytest.raises(AuditRedactionError, match="nested"):
        redact({"run_id": ["never", "export"]})


def test_trace_and_bundle_keep_only_ids_and_no_raw_values(tmp_path) -> None:
    trace = trace_report(
        "run",
        [
            {
                "write_id": "w",
                "calculation_id": "c",
                "trace_id": "t",
                "match_result_id": "m",
                "candidate_id": "candidate",
                "source_row_id": "source",
            }
        ],
    )
    assert trace.links[0]["write_id"] == "w"
    with pytest.raises(ValueError, match="IDs only"):
        trace_report("run", [{"write_id": "w", "raw_values": "secret"}])
    with AuditJournal(tmp_path / "audit.sqlite") as journal:
        run = journal.begin_run(
            ("a" * 64,),
            {"count": 1},
            {"event": "AuditEventEnvelope-16.0"},
            "b" * 64,
            nonce_hex="8" * 32,
        )
        journal.append_event(run.run_id, "RUN", "PENDING")
        bundle = journal.bundle(run.run_id, {"artifact": "c" * 64})
    assert bundle.artifact_hashes == {"artifact": "c" * 64}
