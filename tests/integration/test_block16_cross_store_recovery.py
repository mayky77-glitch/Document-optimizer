"""Recovery validates persisted integrity before any resume."""

from __future__ import annotations

import pytest

from fixtures.audit.builders import run_inputs
from report_processor.audit import (
    AuditErrorCode,
    AuditIntegrityError,
    AuditJournal,
    AuditStage,
    AuditState,
)


def test_reopen_recovery_rejects_mismatched_persisted_hash(tmp_path) -> None:
    path = tmp_path / "audit.sqlite"
    with AuditJournal(path) as journal:
        run = journal.begin_run(*run_inputs(), nonce_hex="5" * 32)
        journal.append_event(run.run_id, AuditStage.RUN, AuditState.PENDING)
        journal.connection.execute("DROP TRIGGER events_no_update")
        journal.connection.execute("UPDATE events SET previous_hash='bad'")
    with AuditJournal(path) as reopened, pytest.raises(AuditIntegrityError) as failure:
        reopened.recover(run.run_id)
    assert failure.value.code is AuditErrorCode.HASH_CHAIN_INVALID


def test_cross_store_hash_mismatches_block_reconcile_and_recovery(tmp_path) -> None:
    path = tmp_path / "audit.sqlite"
    with AuditJournal(path) as journal:
        run = journal.begin_run(*run_inputs(), nonce_hex="9" * 32)
        journal.append_event(run.run_id, "RUN", "PENDING")
        journal.append_event(run.run_id, "DATA", "DATA_COMMITTED")
        journal.record_cross_store_hashes(run.run_id, data_hash="d" * 64, export_hash="e" * 64)
        with pytest.raises(AuditIntegrityError) as data_failure:
            journal.reconcile_cross_store(run.run_id, data_hash="x" * 64, export_hash="e" * 64)
        with pytest.raises(AuditIntegrityError) as export_failure:
            journal.recover(run.run_id, data_hash="d" * 64, export_hash="x" * 64)
    assert data_failure.value.code is AuditErrorCode.SNAPSHOT_CHANGED
    assert export_failure.value.code is AuditErrorCode.EXPORT_HASH_MISMATCH


@pytest.mark.parametrize("completed_boundaries", range(5))
def test_reopen_after_each_saga_crash_point_recovers_only_valid_prefixes(
    tmp_path, completed_boundaries: int
) -> None:
    path = tmp_path / f"crash-{completed_boundaries}.sqlite"
    with AuditJournal(path) as journal:
        run = journal.begin_run(*run_inputs(), nonce_hex=f"{completed_boundaries:x}" * 32)
        lifecycle = (
            ("RUN", "PENDING"),
            ("DATA", "DATA_COMMITTED"),
            ("EXPORT", "EXPORT_PREPARED"),
            ("EXPORT", "EXPORT_VERIFIED"),
        )
        for stage, state in lifecycle[:completed_boundaries]:
            journal.append_event(run.run_id, stage, state)
    with AuditJournal(path) as reopened:
        assert len(reopened.recover(run.run_id).input_ref_hashes) == 2
        assert len(reopened.events(run.run_id)) == completed_boundaries
