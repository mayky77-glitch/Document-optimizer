"""Feedback activation, drift and deterministic compaction."""

from __future__ import annotations

import pytest
from report_processor.audit import (
    AuditErrorCode,
    AuditIntegrityError,
    AuditJournal,
    AuditStage,
    AuditState,
    FeedbackRuleVersion,
)

from fixtures.audit.builders import run_inputs


def test_feedback_stays_inactive_until_verified_and_drift_blocks_activation(tmp_path) -> None:
    with AuditJournal(tmp_path / "audit.sqlite") as journal:
        run = journal.begin_run(*run_inputs(), nonce_hex="3" * 32)
        event = journal.append_event(run.run_id, AuditStage.RUN, AuditState.PENDING)
        feedback = FeedbackRuleVersion("rule-1", run.run_id, event.event_id, "r" * 64, "s" * 64)
        journal.add_feedback(feedback)
        with pytest.raises(AuditIntegrityError, match="EXPORT_VERIFIED"):
            journal.activate_feedback(
                "rule-1", current_rule_hash="r" * 64, current_source_hash="s" * 64
            )
        journal.append_event(run.run_id, AuditStage.DATA, AuditState.DATA_COMMITTED)
        journal.append_event(run.run_id, AuditStage.EXPORT, AuditState.EXPORT_PREPARED)
        journal.append_event(run.run_id, AuditStage.EXPORT, AuditState.EXPORT_VERIFIED)
        with pytest.raises(AuditIntegrityError) as failure:
            journal.activate_feedback(
                "rule-1", current_rule_hash="x" * 64, current_source_hash="s" * 64
            )
    assert failure.value.code is AuditErrorCode.FEEDBACK_DRIFT


def test_compaction_keeps_active_versions_and_never_rewrites_events(tmp_path) -> None:
    with AuditJournal(tmp_path / "audit.sqlite") as journal:
        run = journal.begin_run(*run_inputs(), nonce_hex="4" * 32)
        event = journal.append_event(run.run_id, "RUN", "PENDING")
        journal.add_feedback(
            FeedbackRuleVersion("active", run.run_id, event.event_id, "r" * 64, "s" * 64)
        )
        journal.add_feedback(
            FeedbackRuleVersion("stale", run.run_id, event.event_id, "q" * 64, "s" * 64)
        )
        journal.append_event(run.run_id, "DATA", "DATA_COMMITTED")
        journal.append_event(run.run_id, "EXPORT", "EXPORT_PREPARED")
        journal.append_event(run.run_id, "EXPORT", "EXPORT_VERIFIED")
        journal.activate_feedback(
            "active", current_rule_hash="r" * 64, current_source_hash="s" * 64
        )
        before = journal.events(run.run_id)
        assert journal.compact_feedback() == 1
        assert journal.events(run.run_id) == before
        assert journal.connection.execute("SELECT count(*) FROM feedback").fetchone()[0] == 2
        assert (
            journal.connection.execute("SELECT count(*) FROM feedback_compactions").fetchone()[0]
            == 1
        )


def test_feedback_source_event_from_another_run_is_rejected(tmp_path) -> None:
    with AuditJournal(tmp_path / "audit.sqlite") as journal:
        first = journal.begin_run(*run_inputs(), nonce_hex="6" * 32)
        second = journal.begin_run(*run_inputs(), nonce_hex="7" * 32)
        event = journal.append_event(first.run_id, "RUN", "PENDING")
        foreign = FeedbackRuleVersion("foreign", second.run_id, event.event_id, "r" * 64, "s" * 64)
        with pytest.raises(AuditIntegrityError) as failure:
            journal.add_feedback(foreign)
    assert failure.value.code is AuditErrorCode.FEEDBACK_DRIFT
