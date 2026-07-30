"""Journal integrity, transition and append-only behaviour."""

from __future__ import annotations

import sqlite3

import pytest
from report_processor.audit import (
    AuditErrorCode,
    AuditIntegrityError,
    AuditJournal,
    AuditStage,
    AuditState,
)

from fixtures.audit.builders import run_inputs


def _run(journal: AuditJournal):
    return journal.begin_run(*run_inputs(), nonce_hex="1" * 32)


def test_run_identity_is_deterministic_for_a_persisted_nonce_but_unique_otherwise(tmp_path) -> None:
    with AuditJournal(tmp_path / "audit.sqlite") as journal:
        first = _run(journal)
        resumed = _run(journal)
        distinct = journal.begin_run(*run_inputs(), nonce_hex="2" * 32)
    assert (first.run_key, first.run_id) == (resumed.run_key, resumed.run_id)
    assert first.run_key == distinct.run_key and first.run_id != distinct.run_id


def test_hash_chain_tamper_and_sequence_gap_are_detected(tmp_path) -> None:
    path = tmp_path / "audit.sqlite"
    with AuditJournal(path) as journal:
        run = _run(journal)
        journal.append_event(
            run.run_id,
            AuditStage.RUN,
            AuditState.PENDING,
            timestamp_utc="2026-01-01T00:00:00+00:00",
        )
        journal.append_event(
            run.run_id,
            AuditStage.DATA,
            AuditState.DATA_COMMITTED,
            timestamp_utc="2026-01-01T00:00:01+00:00",
        )
        journal.connection.execute("DROP TRIGGER events_no_update")
        journal.connection.execute("UPDATE events SET event_hash='0' WHERE event_sequence=2")
        with pytest.raises(AuditIntegrityError) as failure:
            journal.validate_run(run.run_id)
    assert failure.value.code is AuditErrorCode.HASH_CHAIN_INVALID


def test_events_are_append_only_and_invalid_transitions_are_rejected(tmp_path) -> None:
    with AuditJournal(tmp_path / "audit.sqlite") as journal:
        run = _run(journal)
        event = journal.append_event(run.run_id, "RUN", "PENDING")
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            journal.connection.execute(
                "UPDATE events SET event_hash='x' WHERE event_id=?", (event.event_id,)
            )
        with pytest.raises(AuditIntegrityError) as failure:
            journal.append_event(run.run_id, "EXPORT", "EXPORT_VERIFIED")
    assert failure.value.code is AuditErrorCode.INVALID_STAGE_TRANSITION
