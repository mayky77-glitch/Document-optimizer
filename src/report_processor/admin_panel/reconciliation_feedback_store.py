"""Private, target-scoped durable reconciliation feedback."""

from __future__ import annotations

import os
import sqlite3
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

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS reconciliation_feedback (
                target_digest TEXT NOT NULL, name_key TEXT NOT NULL, unit_key TEXT,
                action TEXT NOT NULL, category_id TEXT, mode TEXT, sequence INTEGER NOT NULL,
                PRIMARY KEY (target_digest, sequence))"""
            )
        os.chmod(self.path, 0o600)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA journal_mode=DELETE")
        return connection
