"""Private, target-scoped durable reconciliation feedback."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Callable
from pathlib import Path

from report_processor.reconciliation_review import FeedbackRecord, ReviewAction, ReviewMode


class ReconciliationFeedbackStore:
    def __init__(self, workspace_root: Path) -> None:
        self.path = Path(workspace_root) / "reconciliation-feedback.sqlite3"
        self._initialize()

    def records(self, target_digest: str) -> tuple[FeedbackRecord, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT name_key, unit_key, action, category_id, mode, sequence
                FROM reconciliation_feedback WHERE target_digest = ?
                ORDER BY sequence""",
                (target_digest,),
            ).fetchall()
        return tuple(
            FeedbackRecord(
                name_key=row[0],
                unit_key=row[1],
                action=ReviewAction(row[2]),
                target_category=row[3],
                mode=ReviewMode(row[4]) if row[4] else None,
                sequence=int(row[5]),
            )
            for row in rows
        )

    def persist(self, target_digest: str, records: tuple[FeedbackRecord, ...]) -> None:
        """Legacy append-only API. New authoritative applies use ``commit_apply``."""
        with self._connect() as connection:
            next_sequence = int(
                connection.execute(
                    "SELECT COALESCE(MAX(sequence), 0) FROM reconciliation_feedback "
                    "WHERE target_digest = ?",
                    (target_digest,),
                ).fetchone()[0]
            )
            for record in records:
                next_sequence += 1
                connection.execute(
                    """INSERT INTO reconciliation_feedback
                    (target_digest, name_key, unit_key, action, category_id, mode, sequence)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        target_digest,
                        record.name_key,
                        record.unit_key,
                        record.action.value,
                        record.target_category,
                        record.mode.value if record.mode else None,
                        next_sequence,
                    ),
                )

    def commit_apply(
        self,
        *,
        target_digest: str,
        apply_key: str,
        payload_hash: str,
        records: tuple[FeedbackRecord, ...],
        precommit_validator: Callable[[], None] | None = None,
    ) -> bool:
        """Atomically append feedback and record one immutable authoritative apply.

        ``False`` is an exact replay.  A reused key with different payload is a
        controlled conflict: callers must never silently choose an outcome.
        """
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                existing = connection.execute(
                    "SELECT payload_hash FROM reconciliation_applies WHERE apply_key = ?",
                    (apply_key,),
                ).fetchone()
                if existing is not None:
                    if existing[0] != payload_hash:
                        raise ValueError("RECONCILIATION_APPLY_CONFLICT")
                    connection.commit()
                    return False
                next_sequence = int(
                    connection.execute(
                        "SELECT COALESCE(MAX(sequence), 0) FROM reconciliation_feedback "
                        "WHERE target_digest = ?",
                        (target_digest,),
                    ).fetchone()[0]
                )
                for record in records:
                    next_sequence += 1
                    connection.execute(
                        """INSERT INTO reconciliation_feedback
                        (target_digest, name_key, unit_key, action, category_id, mode, sequence)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            target_digest,
                            record.name_key,
                            record.unit_key,
                            record.action.value,
                            record.target_category,
                            record.mode.value if record.mode else None,
                            next_sequence,
                        ),
                    )
                connection.execute(
                    """INSERT INTO reconciliation_applies
                    (apply_key, target_digest, payload_hash) VALUES (?, ?, ?)""",
                    (apply_key, target_digest, payload_hash),
                )
                if precommit_validator is not None:
                    precommit_validator()
                connection.commit()
                return True
            except BaseException:
                connection.rollback()
                raise

    def _initialize(self) -> None:
        with self._connect() as connection:
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if version not in {0, 1, 2}:
                raise RuntimeError("unsupported reconciliation feedback schema")
            legacy_columns = _table_columns(connection, "reconciliation_feedback")
            if legacy_columns is not None and legacy_columns != {
                "target_digest",
                "name_key",
                "unit_key",
                "action",
                "category_id",
                "mode",
                "sequence",
            }:
                raise RuntimeError("unsupported reconciliation feedback schema")
            apply_columns = _table_columns(connection, "reconciliation_applies")
            if apply_columns is not None and apply_columns != {
                "apply_key",
                "target_digest",
                "payload_hash",
            }:
                raise RuntimeError("unsupported reconciliation feedback schema")
            if version == 2 and (legacy_columns is None or apply_columns is None):
                raise RuntimeError("unsupported reconciliation feedback schema")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS reconciliation_feedback (
                target_digest TEXT NOT NULL, name_key TEXT NOT NULL, unit_key TEXT,
                action TEXT NOT NULL, category_id TEXT, mode TEXT, sequence INTEGER NOT NULL,
                PRIMARY KEY (target_digest, sequence))"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS reconciliation_applies (
                apply_key TEXT PRIMARY KEY, target_digest TEXT NOT NULL,
                payload_hash TEXT NOT NULL)"""
            )
            connection.execute("PRAGMA user_version = 2")
        os.chmod(self.path, 0o600)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, isolation_level=None)
        connection.execute("PRAGMA journal_mode=DELETE")
        return connection


def _table_columns(connection: sqlite3.Connection, name: str) -> set[str] | None:
    rows = connection.execute(f"PRAGMA table_info({name})").fetchall()
    return {str(row[1]) for row in rows} if rows else None
