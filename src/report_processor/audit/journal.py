"""Durable append-only SQLite journal with a transactionally checked hash chain."""

from __future__ import annotations

import re
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
    AuditBundle,
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
_CONTROLLED_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_CONTRACT_VALUE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")


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
        if any(
            not isinstance(key, str)
            or not _CONTRACT_VALUE.fullmatch(key)
            or not isinstance(value, str)
            or not _CONTRACT_VALUE.fullmatch(value)
            for key, value in contract_versions.items()
        ):
            raise ValueError("contract_versions must contain controlled version identifiers")
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
        self._validate_controlled_code(reason_code, "reason_code")
        self._validate_controlled_code(warning_code, "warning_code")
        safe_fields = redact(fields or {})
        timestamp = timestamp_utc or datetime.now(UTC).isoformat(timespec="microseconds")
        with self._transaction():
            self.get_run(run_id)
            previous = self.connection.execute(
                "SELECT event_sequence, event_hash, controlled_stage, controlled_state FROM events "
                "WHERE run_id=? ORDER BY event_sequence DESC LIMIT 1",
                (run_id,),
            ).fetchone()
            previous_stage = previous["controlled_stage"] if previous else None
            previous_state = previous["controlled_state"] if previous else None
            if not self._valid_transition(previous_stage, previous_state, stage_value, state_value):
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

    def recover(
        self, run_id: str, *, data_hash: str | None = None, export_hash: str | None = None
    ) -> AuditRun:
        self.validate_run(run_id)
        if data_hash is not None or export_hash is not None:
            self.reconcile_cross_store(run_id, data_hash=data_hash, export_hash=export_hash)
        self.connection.execute("PRAGMA wal_checkpoint(FULL)")
        return self.get_run(run_id)

    def record_cross_store_hashes(
        self, run_id: str, *, data_hash: str, export_hash: str | None = None
    ) -> None:
        """Persist the value-free external-store identity at a durable saga boundary."""
        if not data_hash or (export_hash is not None and not export_hash):
            raise ValueError("cross-store hashes must be non-empty")
        with self._transaction():
            state = self._current_state(run_id)
            if state not in {
                AuditState.DATA_COMMITTED.value,
                AuditState.EXPORT_PREPARED.value,
                AuditState.EXPORT_VERIFIED.value,
            }:
                raise AuditIntegrityError(
                    AuditErrorCode.INVALID_STAGE_TRANSITION,
                    "cross-store hashes require a durable data state",
                )
            prior = self.connection.execute(
                "SELECT data_hash, export_hash FROM cross_store_hashes WHERE run_id=?", (run_id,)
            ).fetchone()
            if prior is not None and (prior["data_hash"], prior["export_hash"]) != (
                data_hash,
                export_hash,
            ):
                raise AuditIntegrityError(
                    AuditErrorCode.SNAPSHOT_CHANGED, "cross-store hashes changed"
                )
            self.connection.execute(
                "INSERT OR IGNORE INTO cross_store_hashes VALUES (?, ?, ?, ?)",
                (run_id, data_hash, export_hash, state),
            )

    def reconcile_cross_store(
        self, run_id: str, *, data_hash: str | None, export_hash: str | None = None
    ) -> None:
        """Block recovery when an external committed-data/export snapshot has drifted."""
        row = self.connection.execute(
            "SELECT data_hash, export_hash, state FROM cross_store_hashes WHERE run_id=?", (run_id,)
        ).fetchone()
        if row is None or data_hash is None or row["data_hash"] != data_hash:
            raise AuditIntegrityError(
                AuditErrorCode.SNAPSHOT_CHANGED, "data-store snapshot changed"
            )
        if export_hash is not None and row["export_hash"] != export_hash:
            raise AuditIntegrityError(
                AuditErrorCode.EXPORT_HASH_MISMATCH, "export snapshot changed"
            )
        if self._current_state(run_id) != row["state"]:
            raise AuditIntegrityError(AuditErrorCode.SNAPSHOT_CHANGED, "saga state changed")

    def bundle(self, run_id: str, artifact_hashes: Mapping[str, str]) -> AuditBundle:
        """Build a value-free bundle after validating the durable event chain."""
        if any(not isinstance(value, str) or not value for value in artifact_hashes.values()):
            raise ValueError("artifact hashes must be controlled identifiers")
        return AuditBundle(self.get_run(run_id), self.validate_run(run_id), dict(artifact_hashes))

    def verify_export(
        self, run_id: str, *, snapshot_hash: str, published_hash: str, attempt_number: int = 1
    ) -> AuditEvent:
        """Advance the export saga only after the published bytes match the snapshot."""
        if snapshot_hash != published_hash:
            raise AuditIntegrityError(
                AuditErrorCode.EXPORT_HASH_MISMATCH, "published export hash differs"
            )
        return self.append_event(
            run_id,
            AuditStage.EXPORT,
            AuditState.EXPORT_VERIFIED,
            fields={"artifact_sha256": snapshot_hash},
            attempt_number=attempt_number,
        )

    def add_feedback(self, version: FeedbackRuleVersion) -> None:
        if not version.rule_content_hash or not version.source_hash:
            raise ValueError("feedback hashes must not be empty")
        with self._transaction():
            source = self.connection.execute(
                "SELECT run_id FROM events WHERE event_id=?", (version.source_event_id,)
            ).fetchone()
            if source is None or source["run_id"] != version.run_id:
                raise AuditIntegrityError(
                    AuditErrorCode.FEEDBACK_DRIFT,
                    "feedback source event does not belong to its run",
                )
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
                "INSERT OR IGNORE INTO feedback_activations VALUES (?, ?, ?)",
                (rule_version_id, current_rule_hash, current_source_hash),
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
            inactive = self.connection.execute(
                "SELECT * FROM feedback WHERE rule_version_id NOT IN "
                "(SELECT rule_version_id FROM feedback_activations) ORDER BY rule_version_id"
            ).fetchall()
            if inactive:
                lineage_hash = digest(tuple(tuple(row) for row in inactive))
                self.connection.execute(
                    "INSERT OR IGNORE INTO feedback_compactions VALUES (?, ?, ?)",
                    (lineage_hash, len(inactive), lineage_hash),
                )
        return len(inactive)

    @staticmethod
    def _validate_controlled_code(value: str | None, field_name: str) -> None:
        if value is not None and (
            not isinstance(value, str) or not _CONTROLLED_CODE.fullmatch(value)
        ):
            raise ValueError(f"{field_name} must be an uppercase controlled code")

    @staticmethod
    def _valid_transition(
        previous_stage: str | None, previous_state: str | None, stage: str, state: str
    ) -> bool:
        expected = {
            None: (AuditStage.RUN.value, AuditState.PENDING.value),
            AuditState.PENDING.value: (AuditStage.DATA.value, AuditState.DATA_COMMITTED.value),
            AuditState.DATA_COMMITTED.value: (
                AuditStage.EXPORT.value,
                AuditState.EXPORT_PREPARED.value,
            ),
            AuditState.EXPORT_PREPARED.value: (
                AuditStage.EXPORT.value,
                AuditState.EXPORT_VERIFIED.value,
            ),
        }.get(previous_state)
        if expected == (stage, state):
            return True
        return previous_stage == stage == AuditStage.DATA.value and previous_state == state == (
            AuditState.DATA_COMMITTED.value
        )

    def _current_state(self, run_id: str) -> str | None:
        row = self.connection.execute(
            "SELECT controlled_state FROM events WHERE run_id=? "
            "ORDER BY event_sequence DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        return row["controlled_state"] if row is not None else None

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
            CREATE TABLE IF NOT EXISTS feedback_compactions(
                lineage_hash TEXT PRIMARY KEY, inactive_count INTEGER NOT NULL,
                compacted_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS feedback_activations(
                rule_version_id TEXT PRIMARY KEY REFERENCES feedback(rule_version_id),
                rule_hash TEXT NOT NULL, source_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cross_store_hashes(
                run_id TEXT PRIMARY KEY REFERENCES runs(run_id), data_hash TEXT NOT NULL,
                export_hash TEXT, state TEXT NOT NULL
            );
            CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
            BEGIN SELECT RAISE(ABORT, 'audit events are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
            BEGIN SELECT RAISE(ABORT, 'audit events are append-only'); END;
            """
        )
