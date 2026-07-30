"""SQLite schema isolated from audit journal behavior."""

from __future__ import annotations

import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    connection.executescript(
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
