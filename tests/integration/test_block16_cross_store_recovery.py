"""Recovery validates persisted integrity before any resume."""

from __future__ import annotations

import pytest
from report_processor.audit import (
    AuditErrorCode,
    AuditIntegrityError,
    AuditJournal,
    AuditStage,
    AuditState,
)

from fixtures.audit.builders import run_inputs


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
