"""Durable append-only SQLite journal with a transactionally checked hash chain."""

from __future__ import annotations

import secrets
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .models import (
    AUDIT_EVENT_VERSION,
    AUDIT_IDENTITY_VERSION,
    GENESIS_EVENT_HASH,
    AuditErrorCode,
    AuditEvent,
    AuditRun,
    AuditStage,
    AuditState,
    FeedbackRuleVersion,
)
from .serialization import canonical_json, digest, event_payload, redact

_TRANSITIONS = {
    None: AuditState.PENDING.value,
    AuditState.PENDING.value: AuditState.DATA_COMMITTED.value,
    AuditState.DATA_COMMITTED.value: AuditState.EXPORT_PREPARED.value,
    AuditState.EXPORT_PREPARED.value: AuditState.EXPORT_VERIFIED.value,
}


class AuditJournalError(RuntimeError):
    pass


class AuditIntegrityError(AuditJournalError):
    def __init__(self, code: AuditErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


class AuditJournal:
    def __init__(self, database_path: Path | str) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.database_path, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA trusted_schema=OFF")
        self.connection.execute("PRAGMA journal_mode=WAL")
        self._migrate()

    def close(self) -> None:
        self.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self.connection.close()

    def __enter__(self) -> AuditJournal:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self.connection.execute("ROLLBACK")
            raise
        else:
            self.connection.execute("COMMIT")

    def begin_run(
        self,
        input_ref_hashes: tuple[str, ...],
        options: Mapping[str, object],
        contract_versions: Mapping[str, str],
        rule_content_hash: str,
        *,
        nonce_hex: str | None = None,
    ) -> AuditRun:
        safe_options = redact(options)
        run_key = digest(
            {
                "inputs": sorted(set(input_ref_hashes)),
                "options": safe_options,
                "contracts": dict(sorted(contract_versions.items())),
                "rule": rule_content_hash,
            }
        )
        nonce_hex = nonce_hex or secrets.token_hex(16)
        if len(nonce_hex) != 32 or any(char not in "0123456789abcdef" for char in nonce_hex):
            raise ValueError("nonce_hex must be a 128-bit lowercase hexadecimal value")
        run_id = digest((AUDIT_IDENTITY_VERSION, run_key, nonce_hex))
        run = AuditRun(
            run_id,
            run_key,
            nonce_hex,
            input_ref_hashes,
            safe_options,
            contract_versions,
            rule_content_hash,
        )
        with self._transaction():
            self.connection.execute(
                "INSERT OR IGNORE INTO runs VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    run_key,
                    nonce_hex,
                    canonical_json(run.input_ref_hashes),
                    canonical_json(safe_options),
                    canonical_json(contract_versions),
                    rule_content_hash,
                ),
            )
        return self.get_run(run_id)

    def get_run(self, run_id: str) -> AuditRun:
        row = self.connection.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        import json

        return AuditRun(
            row["run_id"],
            row["run_key"],
            row["nonce_hex"],
            tuple(json.loads(row["input_refs"])),
            json.loads(row["options"]),
            json.loads(row["contracts"]),
            row["rule_hash"],
        )

    def append_event(
        self,
        run_id: str,
        stage: AuditStage | str,
        state: AuditState | str,
        *,
        reason_code: str | None = None,
        warning_code: str | None = None,
        fields: Mapping[str, object] | None = None,
        attempt_number: int = 1,
        timestamp_utc: str | None = None,
    ) -> AuditEvent:
        stage_value, state_value = str(stage), str(state)
        if stage_value not in {item.value for item in AuditStage} or state_value not in {
            item.value for item in AuditState
        }:
            raise AuditIntegrityError(
                AuditErrorCode.INVALID_STAGE_TRANSITION, "unknown controlled stage/state"
            )
        if attempt_number < 1:
            raise ValueError("attempt_number must be positive")
        safe_fields = redact(fields or {})
        timestamp = timestamp_utc or datetime.now(UTC).isoformat(timespec="microseconds")
        with self._transaction():
            self.get_run(run_id)
            previous = self.connection.execute(
                "SELECT event_sequence, event_hash, controlled_state FROM events "
                "WHERE run_id=? ORDER BY event_sequence DESC LIMIT 1",
                (run_id,),
            ).fetchone()
            previous_state = previous["controlled_state"] if previous else None
            if _TRANSITIONS.get(previous_state) != state_value:
                raise AuditIntegrityError(
                    AuditErrorCode.INVALID_STAGE_TRANSITION,
                    f"{previous_state!r} cannot transition to {state_value}",
                )
            sequence = (previous["event_sequence"] if previous else 0) + 1
            previous_hash = previous["event_hash"] if previous else GENESIS_EVENT_HASH
            stage_attempt_id = digest((AUDIT_IDENTITY_VERSION, run_id, stage_value, attempt_number))
            event_id = digest((run_id, sequence, stage_attempt_id))
            unsigned = {
                "contract_version": AUDIT_EVENT_VERSION,
                "run_id": run_id,
                "event_id": event_id,
                "event_sequence": sequence,
                "stage_attempt_id": stage_attempt_id,
                "controlled_stage_code": stage_value,
                "controlled_state_code": state_value,
                "controlled_reason_code": reason_code,
                "controlled_warning_code": warning_code,
                "previous_event_hash": previous_hash,
                "timestamp_utc": timestamp,
                **safe_fields,
            }
            event_hash = digest(unsigned)
            event = AuditEvent(
                event_id,
                run_id,
                sequence,
                stage_attempt_id,
                stage_value,
                state_value,
                reason_code,
                warning_code,
                previous_hash,
                event_hash,
                timestamp,
                safe_fields,
            )
            self.connection.execute(
                "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event.event_id,
                    event.run_id,
                    event.event_sequence,
                    event.stage_attempt_id,
                    event.controlled_stage_code,
                    event.controlled_state_code,
                    event.controlled_reason_code,
                    event.controlled_warning_code,
                    event.previous_event_hash,
                    event.event_hash,
                    event.timestamp_utc,
                    canonical_json(event.fields),
                ),
            )
        return event

    def events(self, run_id: str) -> tuple[AuditEvent, ...]:
        import json

        rows = self.connection.execute(
            "SELECT * FROM events WHERE run_id=? ORDER BY event_sequence", (run_id,)
        )
        return tuple(
            AuditEvent(
                row["event_id"],
                row["run_id"],
                row["event_sequence"],
                row["stage_attempt_id"],
                row["controlled_stage"],
                row["controlled_state"],
                row["reason_code"],
                row["warning_code"],
                row["previous_hash"],
                row["event_hash"],
                row["timestamp"],
                json.loads(row["fields"]),
            )
            for row in rows
        )

    def validate_run(self, run_id: str) -> tuple[AuditEvent, ...]:
        events = self.events(run_id)
        previous = GENESIS_EVENT_HASH
        for sequence, event in enumerate(events, 1):
            if event.event_sequence != sequence:
                raise AuditIntegrityError(
                    AuditErrorCode.SEQUENCE_GAP, "event sequence contains a gap"
                )
            if event.previous_event_hash != previous:
                raise AuditIntegrityError(
                    AuditErrorCode.HASH_CHAIN_INVALID, "previous event hash differs"
                )
            payload = event_payload(event)
            payload.pop("event_hash")
            if digest(payload) != event.event_hash:
                raise AuditIntegrityError(AuditErrorCode.HASH_CHAIN_INVALID, "event hash differs")
            previous = event.event_hash
        return events

    def recover(self, run_id: str) -> AuditRun:
        self.validate_run(run_id)
        self.connection.execute("PRAGMA wal_checkpoint(FULL)")
        return self.get_run(run_id)

    def add_feedback(self, version: FeedbackRuleVersion) -> None:
        with self._transaction():
            self.connection.execute(
                "INSERT INTO feedback VALUES (?, ?, ?, ?, ?, 0)",
                (
                    version.rule_version_id,
                    version.run_id,
                    version.source_event_id,
                    version.rule_content_hash,
                    version.source_hash,
                ),
            )

    def activate_feedback(
        self, rule_version_id: str, *, current_rule_hash: str, current_source_hash: str
    ) -> FeedbackRuleVersion:
        with self._transaction():
            row = self.connection.execute(
                "SELECT * FROM feedback WHERE rule_version_id=?", (rule_version_id,)
            ).fetchone()
            if row is None:
                raise KeyError(rule_version_id)
            state = self.connection.execute(
                "SELECT controlled_state FROM events WHERE run_id=? "
                "ORDER BY event_sequence DESC LIMIT 1",
                (row["run_id"],),
            ).fetchone()
            if state is None or state[0] != AuditState.EXPORT_VERIFIED.value:
                raise AuditIntegrityError(
                    AuditErrorCode.INVALID_STAGE_TRANSITION, "feedback requires EXPORT_VERIFIED"
                )
            if row["rule_hash"] != current_rule_hash or row["source_hash"] != current_source_hash:
                raise AuditIntegrityError(
                    AuditErrorCode.FEEDBACK_DRIFT, "feedback source or rule changed"
                )
            self.connection.execute(
                "UPDATE feedback SET active=1 WHERE rule_version_id=?", (rule_version_id,)
            )
        return FeedbackRuleVersion(
            row["rule_version_id"],
            row["run_id"],
            row["source_event_id"],
            row["rule_hash"],
            row["source_hash"],
            True,
        )

    def compact_feedback(self) -> int:
        with self._transaction():
            result = self.connection.execute("DELETE FROM feedback WHERE active=0")
        return result.rowcount

    def _migrate(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs(
                run_id TEXT PRIMARY KEY, run_key TEXT NOT NULL, nonce_hex TEXT NOT NULL,
                input_refs TEXT NOT NULL, options TEXT NOT NULL, contracts TEXT NOT NULL,
                rule_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events(
                event_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(run_id),
                event_sequence INTEGER NOT NULL, stage_attempt_id TEXT NOT NULL,
                controlled_stage TEXT NOT NULL, controlled_state TEXT NOT NULL,
                reason_code TEXT, warning_code TEXT, previous_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL, timestamp TEXT NOT NULL, fields TEXT NOT NULL,
                UNIQUE(run_id, event_sequence)
            );
            CREATE TABLE IF NOT EXISTS feedback(
                rule_version_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(run_id),
                source_event_id TEXT NOT NULL REFERENCES events(event_id), rule_hash TEXT NOT NULL,
                source_hash TEXT NOT NULL, active INTEGER NOT NULL
            );
            CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
            BEGIN SELECT RAISE(ABORT, 'audit events are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
            BEGIN SELECT RAISE(ABORT, 'audit events are append-only'); END;
            """
        )
