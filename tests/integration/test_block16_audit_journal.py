"""Journal integrity, transition and append-only behaviour."""

from __future__ import annotations

import sqlite3
import threading

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


def test_true_sequence_gap_is_detected_before_hash_validation(tmp_path) -> None:
    with AuditJournal(tmp_path / "audit.sqlite") as journal:
        run = _run(journal)
        journal.append_event(run.run_id, "RUN", "PENDING")
        journal.append_event(run.run_id, "DATA", "DATA_COMMITTED")
        journal.connection.execute("DROP TRIGGER events_no_update")
        journal.connection.execute("UPDATE events SET event_sequence=3 WHERE event_sequence=2")
        with pytest.raises(AuditIntegrityError) as failure:
            journal.validate_run(run.run_id)
    assert failure.value.code is AuditErrorCode.SEQUENCE_GAP


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


@pytest.mark.parametrize("controlled", ("lowercase", "HAS-DASH", "TOO LONG"))
def test_uncontrolled_reason_and_warning_codes_are_rejected(tmp_path, controlled: str) -> None:
    with AuditJournal(tmp_path / "audit.sqlite") as journal:
        run = _run(journal)
        with pytest.raises(ValueError, match="controlled code"):
            journal.append_event(run.run_id, "RUN", "PENDING", reason_code=controlled)
        with pytest.raises(ValueError, match="controlled code"):
            journal.append_event(run.run_id, "RUN", "PENDING", warning_code=controlled)


def test_concurrent_journals_allocate_one_strict_sequence_per_transition(tmp_path) -> None:
    path = tmp_path / "audit.sqlite"
    with AuditJournal(path) as journal:
        run = _run(journal)
    barrier = threading.Barrier(2)
    outcomes: list[object] = []

    def append_pending() -> None:
        with AuditJournal(path) as connection:
            barrier.wait()
            try:
                outcomes.append(connection.append_event(run.run_id, "RUN", "PENDING"))
            except AuditIntegrityError as exc:
                outcomes.append(exc)

    threads = [threading.Thread(target=append_pending), threading.Thread(target=append_pending)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    with AuditJournal(path) as verified:
        events = verified.validate_run(run.run_id)
    assert [event.event_sequence for event in events] == [1]
    assert sum(isinstance(item, AuditIntegrityError) for item in outcomes) == 1
