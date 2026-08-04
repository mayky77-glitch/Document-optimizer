"""Private append-only SQLite v1 persistence for immutable Wave 4 evidence."""

from __future__ import annotations

import json
import os
import sqlite3
import stat
from contextlib import suppress
from pathlib import Path

from .feedback_graph import create_feedback_graph, derive_contradictions, validate_explicit_edge
from .pattern_models import (
    PATTERN_REGISTRY_STORE_SCHEMA_VERSION,
    PatternIntegrityReport,
    PatternRecord,
    PatternRegistryError,
    PatternRegistryEvent,
    load_feedback_edge,
    load_pattern_record,
    load_pattern_registry_event,
)
from .pattern_registry import RegistryHistory, RegistryOperationPlan

_BUSY_TIMEOUT_MS = 1_000
_TABLES = frozenset({"meta", "records", "pattern_events", "feedback_edges"})
_TRIGGERS = frozenset(
    {
        "records_no_update",
        "records_no_delete",
        "pattern_events_no_update",
        "pattern_events_no_delete",
        "feedback_edges_no_update",
        "feedback_edges_no_delete",
    }
)


def _schema_sql(value: str) -> str:
    return "".join(value.lower().split())


_EXPECTED_OBJECTS = {
    "meta": "create table meta (schema_version integer not null check (schema_version = 1))",
    "records": (
        "create table records (pattern_id text not null, revision integer not null, "
        "fingerprint text not null unique, payload blob not null, "
        "primary key (pattern_id, revision)) without rowid"
    ),
    "pattern_events": (
        "create table pattern_events (pattern_id text not null, revision integer not null, "
        "fingerprint text not null unique, payload blob not null, "
        "primary key (pattern_id, revision), foreign key (pattern_id, revision) "
        "references records(pattern_id, revision)) without rowid"
    ),
    "feedback_edges": (
        "create table feedback_edges (edge_id text primary key, "
        "fingerprint text not null unique, payload blob not null) without rowid"
    ),
    "records_no_update": (
        "create trigger records_no_update before update on records "
        "begin select raise(abort, 'immutable'); end"
    ),
    "records_no_delete": (
        "create trigger records_no_delete before delete on records "
        "begin select raise(abort, 'immutable'); end"
    ),
    "pattern_events_no_update": (
        "create trigger pattern_events_no_update before update on pattern_events "
        "begin select raise(abort, 'immutable'); end"
    ),
    "pattern_events_no_delete": (
        "create trigger pattern_events_no_delete before delete on pattern_events "
        "begin select raise(abort, 'immutable'); end"
    ),
    "feedback_edges_no_update": (
        "create trigger feedback_edges_no_update before update on feedback_edges "
        "begin select raise(abort, 'immutable'); end"
    ),
    "feedback_edges_no_delete": (
        "create trigger feedback_edges_no_delete before delete on feedback_edges "
        "begin select raise(abort, 'immutable'); end"
    ),
}


def _error(code: str, message: str = "private registry store is invalid") -> None:
    raise PatternRegistryError(code, message)


def _payload(model: object) -> bytes:
    from .pattern_models import canonical_payload_bytes

    return canonical_payload_bytes(model)


def _decode(payload: object) -> object:
    if not isinstance(payload, bytes):
        _error("STORE_TAMPERED")
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise PatternRegistryError("STORE_TAMPERED", "private registry store is invalid") from exc


def _require_absolute_path(value: object) -> Path:
    if not isinstance(value, (str, os.PathLike)):
        _error("PATH_INVALID")
    text = os.fspath(value)
    if not isinstance(text, str) or not text or text == ":memory:" or text.startswith("file:"):
        _error("PATH_INVALID")
    path = Path(text)
    if not path.is_absolute():
        _error("PATH_INVALID")
    return path


def _no_symlink_components(path: Path, *, include_leaf: bool) -> None:
    parts = path.parts
    current = Path(parts[0])
    end = len(parts) if include_leaf else len(parts) - 1
    for part in parts[1:end]:
        current /= part
        try:
            information = os.lstat(current)
        except FileNotFoundError:
            _error("PATH_INVALID")
        if stat.S_ISLNK(information.st_mode):
            _error("PATH_UNSAFE")


def _validate_existing_file(path: Path) -> os.stat_result:
    _no_symlink_components(path, include_leaf=True)
    try:
        information = os.lstat(path)
    except FileNotFoundError:
        _error("PATH_INVALID")
    if (
        not stat.S_ISREG(information.st_mode)
        or information.st_nlink != 1
        or information.st_uid != os.getuid()
        or stat.S_IMODE(information.st_mode) != 0o600
    ):
        _error("PATH_UNSAFE")
    return information


class PatternRegistryStore:
    """Fail-closed store; all public writes are explicit append-only transactions."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = _require_absolute_path(path)
        self._created = False
        if self.path.exists():
            before = _validate_existing_file(self.path)
        else:
            _no_symlink_components(self.path, include_leaf=False)
            if not self.path.parent.is_dir():
                _error("PATH_INVALID")
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
            except OSError as exc:
                raise PatternRegistryError(
                    "PATH_INVALID", "private registry store is invalid"
                ) from exc
            os.close(descriptor)
            before = _validate_existing_file(self.path)
            self._created = True
        try:
            self._connection = sqlite3.connect(
                str(self.path), isolation_level=None, timeout=_BUSY_TIMEOUT_MS / 1_000
            )
        except sqlite3.Error as exc:
            raise PatternRegistryError(
                "STORE_OPEN_FAILED", "private registry store is invalid"
            ) from exc
        try:
            connected = _validate_existing_file(self.path)
            if (before.st_dev, before.st_ino) != (connected.st_dev, connected.st_ino):
                _error("PATH_RACE")
            self._file_identity = (connected.st_dev, connected.st_ino)
            self._configure()
            self._initialize_or_verify(before.st_size)
            after = _validate_existing_file(self.path)
            if (after.st_dev, after.st_ino) != self._file_identity:
                _error("PATH_RACE")
        except Exception:
            self._connection.close()
            raise

    def __enter__(self) -> PatternRegistryStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._connection.close()

    def _configure(self) -> None:
        try:
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA trusted_schema = OFF")
            self._connection.execute("PRAGMA journal_mode = DELETE")
            self._connection.execute("PRAGMA synchronous = FULL")
            self._connection.execute("PRAGMA recursive_triggers = ON")
            self._connection.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
        except sqlite3.Error as exc:
            raise PatternRegistryError(
                "STORE_CONFIG_INVALID", "private registry store is invalid"
            ) from exc

    def _initialize_or_verify(self, initial_size: int) -> None:
        version = self._connection.execute("PRAGMA user_version").fetchone()[0]
        tables = {
            row[0]
            for row in self._connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        if version == 0 and not tables and initial_size == 0 and self._created:
            self._create_schema()
        elif version != PATTERN_REGISTRY_STORE_SCHEMA_VERSION:
            _error("SCHEMA_UNSUPPORTED")
        self._verify_schema()

    def _create_schema(self) -> None:
        try:
            self._connection.executescript(
                """
                BEGIN IMMEDIATE;
                CREATE TABLE meta (schema_version INTEGER NOT NULL CHECK (schema_version = 1));
                INSERT INTO meta VALUES (1);
                CREATE TABLE records (
                  pattern_id TEXT NOT NULL, revision INTEGER NOT NULL,
                  fingerprint TEXT NOT NULL UNIQUE,
                  payload BLOB NOT NULL, PRIMARY KEY (pattern_id, revision)
                ) WITHOUT ROWID;
                CREATE TABLE pattern_events (
                  pattern_id TEXT NOT NULL, revision INTEGER NOT NULL,
                  fingerprint TEXT NOT NULL UNIQUE,
                  payload BLOB NOT NULL, PRIMARY KEY (pattern_id, revision),
                  FOREIGN KEY (pattern_id, revision) REFERENCES records(pattern_id, revision)
                ) WITHOUT ROWID;
                CREATE TABLE feedback_edges (
                  edge_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL UNIQUE, payload BLOB NOT NULL
                ) WITHOUT ROWID;
                CREATE TRIGGER records_no_update BEFORE UPDATE ON records
                  BEGIN SELECT RAISE(ABORT, 'immutable'); END;
                CREATE TRIGGER records_no_delete BEFORE DELETE ON records
                  BEGIN SELECT RAISE(ABORT, 'immutable'); END;
                CREATE TRIGGER pattern_events_no_update BEFORE UPDATE ON pattern_events
                  BEGIN SELECT RAISE(ABORT, 'immutable'); END;
                CREATE TRIGGER pattern_events_no_delete BEFORE DELETE ON pattern_events
                  BEGIN SELECT RAISE(ABORT, 'immutable'); END;
                CREATE TRIGGER feedback_edges_no_update BEFORE UPDATE ON feedback_edges
                  BEGIN SELECT RAISE(ABORT, 'immutable'); END;
                CREATE TRIGGER feedback_edges_no_delete BEFORE DELETE ON feedback_edges
                  BEGIN SELECT RAISE(ABORT, 'immutable'); END;
                PRAGMA user_version = 1;
                COMMIT;
                """
            )
        except sqlite3.Error as exc:
            raise PatternRegistryError(
                "SCHEMA_CREATE_FAILED", "private registry store is invalid"
            ) from exc

    def _verify_schema(self) -> None:
        try:
            version = self._connection.execute("PRAGMA user_version").fetchone()[0]
            tables = {
                row[0]
                for row in self._connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' "
                    "AND name NOT LIKE 'sqlite_%'"
                )
            }
            triggers = {
                row[0]
                for row in self._connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'trigger'"
                )
            }
            meta = self._connection.execute("SELECT schema_version FROM meta").fetchall()
            foreign = self._connection.execute("PRAGMA foreign_keys").fetchone()[0]
            trusted = self._connection.execute("PRAGMA trusted_schema").fetchone()[0]
            recursive = self._connection.execute("PRAGMA recursive_triggers").fetchone()[0]
            journal = self._connection.execute("PRAGMA journal_mode").fetchone()[0]
            synchronous = self._connection.execute("PRAGMA synchronous").fetchone()[0]
            busy_timeout = self._connection.execute("PRAGMA busy_timeout").fetchone()[0]
            objects = {
                row[0]: row[1]
                for row in self._connection.execute(
                    "SELECT name, sql FROM sqlite_master "
                    "WHERE type IN ('table', 'trigger') AND name NOT LIKE 'sqlite_%'"
                )
            }
            if (
                version != 1
                or tables != _TABLES
                or triggers != _TRIGGERS
                or meta != [(1,)]
                or foreign != 1
                or trusted != 0
                or recursive != 1
                or journal != "delete"
                or synchronous != 2
                or busy_timeout != _BUSY_TIMEOUT_MS
                or set(objects) != set(_EXPECTED_OBJECTS)
                or any(
                    _schema_sql(objects[name]) != _schema_sql(sql)
                    for name, sql in _EXPECTED_OBJECTS.items()
                )
            ):
                _error("SCHEMA_TAMPERED")
            if self._connection.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                _error("STORE_TAMPERED")
            if self._connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                _error("STORE_TAMPERED")
        except sqlite3.Error as exc:
            raise PatternRegistryError(
                "SCHEMA_TAMPERED", "private registry store is invalid"
            ) from exc

    def _transaction(self) -> None:
        self._preflight()
        try:
            self._connection.execute("BEGIN IMMEDIATE")
        except sqlite3.Error as exc:
            raise PatternRegistryError("STORE_BUSY", "private registry store is invalid") from exc

    def _execute(self, sql: str, params: tuple[object, ...] = ()) -> sqlite3.Cursor:
        """Private SQL seam for deterministic rollback tests; never a public failpoint."""
        return self._connection.execute(sql, params)

    def _preflight(self) -> None:
        information = _validate_existing_file(self.path)
        if (information.st_dev, information.st_ino) != self._file_identity:
            _error("PATH_RACE")
        self._verify_schema()

    def _rollback(self) -> None:
        with suppress(sqlite3.Error):
            self._connection.execute("ROLLBACK")

    def _record_row(self, pattern_id: str, revision: int) -> tuple[object, ...] | None:
        return self._connection.execute(
            "SELECT fingerprint, payload FROM records WHERE pattern_id = ? AND revision = ?",
            (pattern_id, revision),
        ).fetchone()

    def _head(self, pattern_id: str) -> tuple[int, str] | None:
        return self._connection.execute(
            "SELECT revision, fingerprint FROM records WHERE pattern_id = ? "
            "ORDER BY revision DESC LIMIT 1",
            (pattern_id,),
        ).fetchone()

    def _validate_record_conflicts(self, record: PatternRecord) -> None:
        if record.state.value == "owner_approved" and record.contradictions:
            _error("CONFLICT_STATE_UNREPRESENTABLE")
        if record.state.value == "active" and record.contradictions:
            _error("ACTIVE_CONFLICT_REQUIRES_SUSPENSION")
        for contradiction in record.contradictions:
            placeholders = ",".join("?" for _ in contradiction.evidence_fingerprints)
            rows = self._connection.execute(
                f"SELECT fingerprint FROM feedback_edges WHERE fingerprint IN ({placeholders})",
                contradiction.evidence_fingerprints,
            ).fetchall()
            if tuple(sorted(row[0] for row in rows)) != contradiction.evidence_fingerprints:
                _error("CONTRADICTION_EVIDENCE_UNKNOWN")

    def _require_current_records(self, records: tuple[PatternRecord, ...]) -> None:
        if not isinstance(records, tuple) or any(
            not isinstance(record, PatternRecord) for record in records
        ):
            _error("PATTERN_EVIDENCE_INVALID")
        for record in records:
            if self._head(record.pattern_id) != (record.revision, record.fingerprint):
                _error("UNKNOWN_PATTERN_ENDPOINT")

    def _append_pair(self, record: PatternRecord, event: PatternRegistryEvent) -> None:
        if (
            event.pattern_id != record.pattern_id
            or event.revision != record.revision
            or event.payload_fingerprint != record.fingerprint
        ):
            _error("RECORD_EVENT_MISMATCH")
        self._validate_record_conflicts(record)
        existing_record = self._record_row(record.pattern_id, record.revision)
        existing_event = self._connection.execute(
            "SELECT fingerprint, payload FROM pattern_events WHERE pattern_id = ? AND revision = ?",
            (event.pattern_id, event.revision),
        ).fetchone()
        if existing_record is not None or existing_event is not None:
            if existing_record is None or existing_event is None:
                _error("PARTIAL_REPLAY")
            if (
                existing_record[0] == record.fingerprint
                and existing_event[0] == event.fingerprint
                and existing_record[1] == _payload(record)
                and existing_event[1] == _payload(event)
            ):
                return
            _error("IDENTITY_CONFLICT")
        head = self._head(record.pattern_id)
        if record.revision == 1:
            if (
                head is not None
                or record.previous_fingerprint is not None
                or event.previous_event_fingerprint is not None
            ):
                _error("STALE_HEAD")
        else:
            if head != (record.revision - 1, record.previous_fingerprint):
                _error("STALE_HEAD")
            prior_event = self._connection.execute(
                "SELECT fingerprint FROM pattern_events WHERE pattern_id = ? AND revision = ?",
                (record.pattern_id, record.revision - 1),
            ).fetchone()
            if prior_event is None or prior_event[0] != event.previous_event_fingerprint:
                _error("EVENT_CHAIN_INVALID")
        try:
            self._execute(
                "INSERT INTO records VALUES (?, ?, ?, ?)",
                (record.pattern_id, record.revision, record.fingerprint, _payload(record)),
            )
            self._execute(
                "INSERT INTO pattern_events VALUES (?, ?, ?, ?)",
                (event.pattern_id, event.revision, event.fingerprint, _payload(event)),
            )
        except sqlite3.Error as exc:
            raise PatternRegistryError(
                "STORE_WRITE_FAILED", "private registry store is invalid"
            ) from exc

    def _pair_status(self, record: PatternRecord, event: PatternRegistryEvent) -> str:
        stored_record = self._record_row(record.pattern_id, record.revision)
        stored_event = self._connection.execute(
            "SELECT fingerprint, payload FROM pattern_events WHERE pattern_id = ? AND revision = ?",
            (event.pattern_id, event.revision),
        ).fetchone()
        if stored_record is None and stored_event is None:
            return "absent"
        if stored_record is None or stored_event is None:
            return "partial"
        if stored_record == (record.fingerprint, _payload(record)) and stored_event == (
            event.fingerprint,
            _payload(event),
        ):
            return "exact"
        return "conflict"

    def _history_write_start(self, history: RegistryHistory) -> int | None:
        statuses = tuple(
            self._pair_status(record, event)
            for record, event in zip(history.records, history.events, strict=True)
        )
        if "partial" in statuses:
            _error("PARTIAL_REPLAY")
        if "conflict" in statuses:
            _error("IDENTITY_CONFLICT")
        first_absent = next(
            (index for index, status in enumerate(statuses) if status == "absent"), None
        )
        if first_absent is None:
            if self._head(history.head.pattern_id) == (
                history.head.revision,
                history.head.fingerprint,
            ):
                return None
            _error("STALE_HEAD")
        if any(status != "absent" for status in statuses[first_absent:]):
            _error("PARTIAL_REPLAY")
        if first_absent:
            predecessor = history.records[first_absent - 1]
            if self._head(predecessor.pattern_id) != (
                predecessor.revision,
                predecessor.fingerprint,
            ):
                _error("STALE_HEAD")
        return first_absent

    def append_history(self, history: RegistryHistory) -> None:
        if not isinstance(history, RegistryHistory):
            _error("HISTORY_INVALID")
        self._transaction()
        try:
            start = self._history_write_start(history)
            if start is None:
                self._connection.execute("COMMIT")
                return
            for record, event in zip(history.records[start:], history.events[start:], strict=True):
                self._append_pair(record, event)
            self._connection.execute("COMMIT")
        except Exception:
            self._rollback()
            raise

    def apply_plan(self, plan: RegistryOperationPlan) -> None:
        if not isinstance(plan, RegistryOperationPlan):
            _error("PLAN_INVALID")
        self._transaction()
        try:
            statuses = tuple(
                self._pair_status(record, event)
                for record, event in zip(plan.appended_records, plan.appended_events, strict=True)
            )
            if "partial" in statuses or ("exact" in statuses and "absent" in statuses):
                _error("PARTIAL_REPLAY")
            if "conflict" in statuses:
                _error("IDENTITY_CONFLICT")
            if statuses and all(status == "exact" for status in statuses):
                final_records = {record.pattern_id: record for record in plan.appended_records}
                if all(
                    self._head(pattern_id) == (record.revision, record.fingerprint)
                    for pattern_id, record in final_records.items()
                ):
                    self._connection.execute("COMMIT")
                    return
                _error("STALE_HEAD")
            for head in plan.expected_heads:
                if self._head(head.pattern_id) != (head.revision, head.fingerprint):
                    _error("STALE_HEAD")
            for record, event in zip(plan.appended_records, plan.appended_events, strict=True):
                self._append_pair(record, event)
            self._connection.execute("COMMIT")
        except Exception:
            self._rollback()
            raise

    def append_edge(self, edge: object, *, records: tuple[PatternRecord, ...]) -> None:
        try:
            validate_explicit_edge(edge, records=records)  # type: ignore[arg-type]
        except PatternRegistryError:
            raise
        self._transaction()
        try:
            self._require_current_records(records)
            current = self.load_graph()
            combined = create_feedback_graph(edges=(*current.edges, edge))
            if derive_contradictions(current) != derive_contradictions(combined):
                _error("CONFLICT_REVISIONS_REQUIRED")
            existing = self._connection.execute(
                "SELECT fingerprint, payload FROM feedback_edges WHERE edge_id = ?", (edge.edge_id,)
            ).fetchone()
            payload = _payload(edge)
            if existing is not None:
                if existing == (edge.fingerprint, payload):
                    self._connection.execute("COMMIT")
                    return
                _error("IDENTITY_CONFLICT")
            self._execute(
                "INSERT INTO feedback_edges VALUES (?, ?, ?)",
                (edge.edge_id, edge.fingerprint, payload),
            )
            self._connection.execute("COMMIT")
        except Exception:
            self._rollback()
            raise

    def append_edge_and_revisions(
        self,
        edge: object,
        *,
        records: tuple[PatternRecord, ...],
        revisions: tuple[tuple[PatternRecord, PatternRegistryEvent], ...],
        expected_heads: tuple[PatternRecord, ...],
    ) -> None:
        validate_explicit_edge(edge, records=records)  # type: ignore[arg-type]
        self._transaction()
        try:
            existing = self._connection.execute(
                "SELECT fingerprint, payload FROM feedback_edges WHERE edge_id = ?", (edge.edge_id,)
            ).fetchone()
            payload = _payload(edge)
            statuses = tuple(self._pair_status(record, event) for record, event in revisions)
            if existing is not None:
                if existing != (edge.fingerprint, payload) or "conflict" in statuses:
                    _error("IDENTITY_CONFLICT")
                if not revisions or "partial" in statuses or "absent" in statuses:
                    _error("PARTIAL_REPLAY")
                if all(
                    self._head(record.pattern_id) == (record.revision, record.fingerprint)
                    for record, _ in revisions
                ):
                    self._connection.execute("COMMIT")
                    return
                _error("PARTIAL_REPLAY")
            self._require_current_records(records)
            current = self.load_graph()
            combined = create_feedback_graph(edges=(*current.edges, edge))
            prior_ids = {item.contradiction_id for item in derive_contradictions(current)}
            additions = tuple(
                item
                for item in derive_contradictions(combined)
                if item.contradiction_id not in prior_ids
            )
            affected = tuple(
                sorted(
                    {
                        pattern_id
                        for item in additions
                        for pattern_id in (item.left_pattern_id, item.right_pattern_id)
                    }
                )
            )
            heads_by_id = {head.pattern_id: head for head in expected_heads}
            revisions_by_id = {record.pattern_id: (record, event) for record, event in revisions}
            if (
                tuple(sorted(heads_by_id)) != affected
                or len(heads_by_id) != len(expected_heads)
                or tuple(sorted(revisions_by_id)) != affected
                or len(revisions_by_id) != len(revisions)
                or tuple(head.pattern_id for head in expected_heads) != affected
                or tuple(record.pattern_id for record, _ in revisions) != affected
            ):
                _error("CONFLICT_REVISIONS_INVALID")
            for head in expected_heads:
                if self._head(head.pattern_id) != (head.revision, head.fingerprint):
                    _error("STALE_HEAD")
            for pattern_id in affected:
                head = heads_by_id[pattern_id]
                record, event = revisions_by_id[pattern_id]
                expected_contradictions = tuple(
                    item
                    for item in derive_contradictions(combined)
                    if pattern_id in {item.left_pattern_id, item.right_pattern_id}
                )
                if head.state.value in {"owner_approved", "suspended", "retired"}:
                    _error("CONFLICT_STATE_UNREPRESENTABLE")
                expected_state = "suspended" if head.state.value == "active" else head.state.value
                expected_event = (
                    "conflict_suspended" if expected_state == "suspended" else "state_transition"
                )
                if (
                    record.revision != head.revision + 1
                    or record.previous_fingerprint != head.fingerprint
                    or record.state.value != expected_state
                    or record.contradictions != expected_contradictions
                    or event.event_type.value != expected_event
                ):
                    _error("CONFLICT_REVISIONS_INVALID")
            existing = self._connection.execute(
                "SELECT fingerprint, payload FROM feedback_edges WHERE edge_id = ?", (edge.edge_id,)
            ).fetchone()
            payload = _payload(edge)
            statuses = tuple(self._pair_status(record, event) for record, event in revisions)
            if "partial" in statuses or ("exact" in statuses and "absent" in statuses):
                _error("PARTIAL_REPLAY")
            if "conflict" in statuses:
                _error("IDENTITY_CONFLICT")
            if existing is not None and all(status == "exact" for status in statuses):
                if all(
                    self._head(record.pattern_id) == (record.revision, record.fingerprint)
                    for record, _ in revisions
                ):
                    self._connection.execute("COMMIT")
                    return
                _error("PARTIAL_REPLAY")
            if existing is not None:
                _error("PARTIAL_REPLAY")
            if existing is None:
                self._execute(
                    "INSERT INTO feedback_edges VALUES (?, ?, ?)",
                    (edge.edge_id, edge.fingerprint, payload),
                )
            elif existing != (edge.fingerprint, payload):
                _error("IDENTITY_CONFLICT")
            for record, event in revisions:
                self._append_pair(record, event)
            self._connection.execute("COMMIT")
        except Exception:
            self._rollback()
            raise

    def _load_history_rows(self, pattern_id: str) -> RegistryHistory:
        records = self._connection.execute(
            "SELECT pattern_id, revision, fingerprint, payload FROM records "
            "WHERE pattern_id = ? ORDER BY revision",
            (pattern_id,),
        ).fetchall()
        events = self._connection.execute(
            "SELECT pattern_id, revision, fingerprint, payload FROM pattern_events "
            "WHERE pattern_id = ? ORDER BY revision",
            (pattern_id,),
        ).fetchall()
        if not records:
            _error("PATTERN_NOT_FOUND")
        if len(records) != len(events):
            _error("EVENT_CHAIN_INVALID")
        loaded_records = []
        loaded_events = []
        for raw in records:
            record = load_pattern_record(_decode(raw[3]))
            if (record.pattern_id, record.revision, record.fingerprint) != tuple(
                raw[:3]
            ) or _payload(record) != raw[3]:
                _error("STORE_TAMPERED")
            loaded_records.append(record)
        for raw in events:
            event = load_pattern_registry_event(_decode(raw[3]))
            if (event.pattern_id, event.revision, event.fingerprint) != tuple(raw[:3]) or _payload(
                event
            ) != raw[3]:
                _error("STORE_TAMPERED")
            loaded_events.append(event)
        history = RegistryHistory(tuple(loaded_records), tuple(loaded_events))
        self._validate_history_semantics(history)
        return history

    def _validate_history_semantics(self, history: RegistryHistory) -> None:
        for index, (record, event) in enumerate(zip(history.records, history.events, strict=True)):
            if index == 0:
                if event.event_type.value != "candidate_registered":
                    _error("EVENT_SEMANTICS_INVALID")
                continue
            prior = history.records[index - 1]
            if prior.state is record.state:
                if (
                    record.state.value not in {"proposed", "shadow"}
                    or not record.contradictions
                    or event.event_type.value != "state_transition"
                ):
                    _error("EVENT_SEMANTICS_INVALID")
                continue
            if prior.state.value == "owner_approved" and record.state.value == "active":
                if event.event_type.value != "wave5_verified_import":
                    _error("EVENT_SEMANTICS_INVALID")
            else:
                from .pattern_models import validate_state_transition

                validate_state_transition(prior.state, record.state)
                expected = (
                    "conflict_suspended"
                    if record.state.value == "suspended" and record.contradictions
                    else "rolled_back"
                    if record.rollback is not None
                    else "superseded"
                    if record.superseded_by_pattern_id is not None
                    else "state_transition"
                )
                if event.event_type.value != expected:
                    _error("EVENT_SEMANTICS_INVALID")

    def load_history(self, pattern_id: str) -> RegistryHistory:
        try:
            self._preflight()
            return self._load_history_rows(pattern_id)
        except PatternRegistryError:
            raise
        except (sqlite3.Error, TypeError, ValueError) as exc:
            raise PatternRegistryError(
                "STORE_TAMPERED", "private registry store is invalid"
            ) from exc

    def _current_records(self) -> tuple[PatternRecord, ...]:
        pattern_ids = tuple(
            row[0]
            for row in self._connection.execute(
                "SELECT DISTINCT pattern_id FROM records ORDER BY pattern_id"
            )
        )
        return tuple(self._load_history_rows(pattern_id).head for pattern_id in pattern_ids)

    def load_graph(self):
        try:
            self._preflight()
            edges = tuple(
                load_feedback_edge(_decode(row[0]))
                for row in self._connection.execute(
                    "SELECT payload FROM feedback_edges ORDER BY edge_id"
                )
            )
            records = self._current_records()
            for edge in edges:
                validate_explicit_edge(edge, records=records)
            return create_feedback_graph(edges=edges)
        except PatternRegistryError:
            raise
        except (sqlite3.Error, TypeError, ValueError) as exc:
            raise PatternRegistryError(
                "STORE_TAMPERED", "private registry store is invalid"
            ) from exc

    def integrity_report(self, pattern_id: str) -> PatternIntegrityReport:
        history = self.load_history(pattern_id)
        graph = self.load_graph()
        head = history.head
        incident = tuple(
            edge
            for edge in graph.edges
            if head.pattern_id in {edge.source.pattern_id, edge.target.pattern_id}
        )
        from .feedback_graph import derive_contradictions

        expected = tuple(
            item
            for item in derive_contradictions(create_feedback_graph(edges=incident))
            if head.pattern_id in {item.left_pattern_id, item.right_pattern_id}
        )
        issues = () if head.contradictions == expected else ("CONTRADICTION_MISMATCH",)
        return PatternIntegrityReport(
            pattern_id=head.pattern_id,
            checked_revision=head.revision,
            record_fingerprint=head.fingerprint,
            event_fingerprints=tuple(sorted(event.fingerprint for event in history.events)),
            edge_fingerprints=tuple(sorted(edge.fingerprint for edge in incident)),
            contradiction_ids=tuple(sorted(item.contradiction_id for item in head.contradictions)),
            valid=not issues,
            issues=issues,
        )
