"""Transactional DuckDB implementation of the isolated analytical store."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from contextlib import suppress
from pathlib import Path
from types import MappingProxyType
from typing import Any

import duckdb

from report_processor.business_rules.models import ValidatedRuleSet
from report_processor.normalization.models import NormalizedSourceRow
from report_processor.target_report.models import TargetReportRow

from .exceptions import (
    AnalyticalError,
    AnalyticalExportError,
    AnalyticalMigrationError,
    AnalyticalQueryError,
    AnalyticalWriteError,
)
from .export import write_diagnostics_temp
from .models import (
    ANALYTICAL_SCHEMA_VERSION,
    MAX_QUERY_LIMIT,
    AnalyticalExportResult,
    AnalyticalLoadResult,
    AnalyticalQuery,
    AnalyticalQueryResult,
)
from .preparation import (
    RULE_CLAUSE_COLUMNS,
    RULE_SET_COLUMNS,
    SOURCE_COLUMNS,
    TARGET_COLUMNS,
    prepare_rule_set,
    prepare_source_rows,
    prepare_target_rows,
)
from .schema import application_tables, create_database_schema, validate_existing_database
from .serialization import deterministic_json

_QUERY_SPECS: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
    "source_rows": (
        "SELECT * FROM v_source_rows",
        ("source_row_id", "line_id", "source_file_id"),
        ("source_row_id",),
    ),
    "target_rows": (
        "SELECT * FROM v_target_rows",
        ("target_row_id", "target_source_id", "target_fingerprint", "sheet_name"),
        ("target_source_id", "target_fingerprint", "sheet_name", "row_number", "target_row_id"),
    ),
    "rule_clauses": (
        "SELECT * FROM v_rule_clauses",
        ("content_hash", "rule_id"),
        ("content_hash", "rule_id", "clause_index"),
    ),
    "diagnostics": (
        "SELECT * FROM v_diagnostics",
        ("entity_type", "entity_id"),
        ("entity_type", "entity_id", "warning_index"),
    ),
}


class AnalyticalStore:
    """Independent analytical database; it never opens or changes storage v1."""

    def __init__(
        self, database_path: Path | str, *, create_parent: bool = True, read_only: bool = False
    ) -> None:
        self.database_path = Path(database_path)
        self._connection: duckdb.DuckDBPyConnection | None = None
        self._open(create_parent=create_parent, read_only=read_only)

    def __enter__(self) -> AnalyticalStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    @property
    def schema_version(self) -> str:
        return ANALYTICAL_SCHEMA_VERSION

    def load_source_rows(self, rows: Iterable[NormalizedSourceRow]) -> AnalyticalLoadResult:
        prepared, received, duplicate_count, warnings = prepare_source_rows(rows)
        inserted, unchanged = self._load_rows(
            table="source_rows", key_column="source_row_id", values=prepared, warnings=warnings
        )
        return AnalyticalLoadResult(
            self.database_path, "source_rows", received, inserted, unchanged + duplicate_count
        )

    def load_target_rows(
        self,
        rows: Iterable[TargetReportRow],
        *,
        target_source_id: str,
        target_fingerprint: str,
    ) -> AnalyticalLoadResult:
        if not isinstance(target_source_id, str) or not target_source_id:
            raise AnalyticalWriteError("target_source_id не может быть пустым")
        if not isinstance(target_fingerprint, str) or not target_fingerprint:
            raise AnalyticalWriteError("target_fingerprint не может быть пустым")
        prepared, received, duplicate_count, warnings = prepare_target_rows(
            rows, target_source_id, target_fingerprint
        )
        inserted, unchanged = self._load_rows(
            table="target_rows", key_column="target_row_id", values=prepared, warnings=warnings
        )
        return AnalyticalLoadResult(
            self.database_path, "target_rows", received, inserted, unchanged + duplicate_count
        )

    def load_rule_set(self, rule_set: ValidatedRuleSet) -> AnalyticalLoadResult:
        values, clauses = prepare_rule_set(rule_set)
        payload_digest = values[-1]
        try:
            connection = self._require_connection()
            connection.execute("BEGIN TRANSACTION")
            existing = self._hash_for_key("rule_sets", "content_hash", rule_set.content_hash)
            if existing is not None and existing != payload_digest:
                raise AnalyticalWriteError("content_hash уже существует с другим payload")
            if existing is None:
                self._insert_many("rule_sets", RULE_SET_COLUMNS, [values])
                if clauses:
                    self._insert_many("rule_clauses", RULE_CLAUSE_COLUMNS, clauses)
                inserted, unchanged = 1, 0
            else:
                inserted, unchanged = 0, 1
            connection.execute("COMMIT")
        except AnalyticalError:
            self._rollback_quietly()
            raise
        except (duckdb.Error, ValueError, TypeError) as exc:
            self._rollback_quietly()
            raise AnalyticalWriteError(f"Не удалось атомарно сохранить rule set: {exc}") from exc
        return AnalyticalLoadResult(self.database_path, "rule_sets", 1, inserted, unchanged)

    def query(self, query: AnalyticalQuery | None = None) -> AnalyticalQueryResult:
        query = AnalyticalQuery() if query is None else query
        if not isinstance(query, AnalyticalQuery):
            raise AnalyticalQueryError("query должен быть AnalyticalQuery или None")
        if query.name not in _QUERY_SPECS:
            raise AnalyticalQueryError("Поддерживается только фиксированный named query")
        if (
            isinstance(query.limit, bool)
            or not isinstance(query.limit, int)
            or not 1 <= query.limit <= MAX_QUERY_LIMIT
        ):
            raise AnalyticalQueryError(f"limit должен быть целым числом от 1 до {MAX_QUERY_LIMIT}")
        select_sql, allowed_filters, order = _QUERY_SPECS[query.name]
        unknown = set(query.filters) - set(allowed_filters)
        if unknown:
            raise AnalyticalQueryError(f"Недопустимые фильтры: {', '.join(sorted(unknown))}")
        clauses, parameters = [], []
        for name, value in query.filters.items():
            clauses.append(f"{name} = ?")
            parameters.append(value)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"{select_sql}{where} ORDER BY {', '.join(order)} LIMIT ?"
        parameters.append(query.limit)
        try:
            cursor = self._require_connection().execute(sql, parameters)
            columns = tuple(item[0] for item in cursor.description)
            rows = tuple(
                MappingProxyType(dict(zip(columns, record, strict=True)))
                for record in cursor.fetchall()
            )
        except duckdb.Error as exc:
            raise AnalyticalQueryError(f"Не удалось выполнить named query: {exc}") from exc
        return AnalyticalQueryResult(query.name, columns, rows)

    def export_diagnostics_jsonl(self, output_path: Path | str) -> AnalyticalExportResult:
        output = Path(output_path)
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            records = self.query(AnalyticalQuery(name="diagnostics", limit=MAX_QUERY_LIMIT)).rows
            temp_path, count, byte_count = write_diagnostics_temp(output, records)
            try:
                os.replace(temp_path, output)
            except OSError:
                temp_path.unlink(missing_ok=True)
                raise
        except AnalyticalError:
            raise
        except (OSError, TypeError, ValueError) as exc:
            raise AnalyticalExportError(
                f"Не удалось атомарно экспортировать diagnostics JSONL: {exc}"
            ) from exc
        return AnalyticalExportResult(output, count, byte_count)

    def _open(self, *, create_parent: bool, read_only: bool) -> None:
        if self.database_path != Path(":memory:"):
            parent = self.database_path.parent
            try:
                if read_only and not self.database_path.is_file():
                    raise FileNotFoundError(self.database_path)
                if create_parent and not read_only:
                    parent.mkdir(parents=True, exist_ok=True)
                elif not parent.is_dir():
                    raise FileNotFoundError(parent)
            except OSError as exc:
                raise AnalyticalMigrationError(
                    f"Не удалось подготовить каталог analytical DB: {exc}"
                ) from exc
        try:
            self._connection = duckdb.connect(str(self.database_path), read_only=read_only)
            if read_only:
                validate_existing_database(self._require_connection())
            else:
                self._migrate()
        except (AnalyticalError, duckdb.Error) as exc:
            self.close()
            if isinstance(exc, AnalyticalError):
                raise
            raise AnalyticalMigrationError(f"Не удалось открыть analytical DuckDB: {exc}") from exc

    def _migrate(self) -> None:
        connection = self._require_connection()
        try:
            connection.execute("BEGIN TRANSACTION")
            tables = application_tables(connection)
            if not tables:
                create_database_schema(connection)
            else:
                validate_existing_database(connection)
            connection.execute("COMMIT")
        except AnalyticalError:
            self._rollback_quietly()
            raise
        except duckdb.Error as exc:
            self._rollback_quietly()
            raise AnalyticalMigrationError(
                f"Не удалось применить analytical schema: {exc}"
            ) from exc

    def _load_rows(
        self,
        *,
        table: str,
        key_column: str,
        values: dict[str, tuple[Any, ...]],
        warnings: dict[str, tuple[str, ...]],
    ) -> tuple[int, int]:
        columns = SOURCE_COLUMNS if table == "source_rows" else TARGET_COLUMNS
        try:
            connection = self._require_connection()
            connection.execute("BEGIN TRANSACTION")
            existing = self._existing_hashes(table, key_column, values)
            conflicts = [
                key
                for key, value in values.items()
                if key in existing and existing[key] != value[1]
            ]
            if conflicts:
                raise AnalyticalWriteError(
                    f"{key_column} уже существует с другим payload: {conflicts[0]}"
                )
            new_rows = [value for key, value in values.items() if key not in existing]
            if new_rows:
                self._insert_many(table, columns, new_rows)
                self._insert_warnings(
                    table, {key: warnings[key] for key in values if key not in existing}
                )
            connection.execute("COMMIT")
        except AnalyticalError:
            self._rollback_quietly()
            raise
        except duckdb.Error as exc:
            self._rollback_quietly()
            raise AnalyticalWriteError(f"Не удалось атомарно сохранить {table}: {exc}") from exc
        return len(new_rows), len(values) - len(new_rows)

    def _existing_hashes(
        self, table: str, key_column: str, values: Mapping[str, tuple[Any, ...]]
    ) -> dict[str, str]:
        if not values:
            return {}
        placeholders = ", ".join("?" for _ in values)
        rows = (
            self._require_connection()
            .execute(
                f"SELECT {key_column}, payload_hash FROM {table} "
                f"WHERE {key_column} IN ({placeholders})",
                list(values),
            )
            .fetchall()
        )
        return {key: digest for key, digest in rows}

    def _hash_for_key(self, table: str, key_column: str, key: str) -> str | None:
        row = (
            self._require_connection()
            .execute(f"SELECT payload_hash FROM {table} WHERE {key_column} = ?", [key])
            .fetchone()
        )
        return None if row is None else row[0]

    def _insert_many(
        self, table: str, columns: tuple[str, ...], values: list[tuple[Any, ...]]
    ) -> None:
        if values:
            placeholders = ", ".join("?" for _ in columns)
            sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
            self._require_connection().executemany(sql, values)

    def _insert_warnings(self, entity_type: str, items: Mapping[str, tuple[str, ...]]) -> None:
        values = [
            (
                entity_type,
                entity_id,
                index,
                warning,
                deterministic_json({"entity_type": entity_type, "entity_id": entity_id}),
            )
            for entity_id, warnings in sorted(items.items())
            for index, warning in enumerate(warnings)
        ]
        self._insert_many(
            "warnings",
            ("entity_type", "entity_id", "warning_index", "warning", "provenance_json"),
            values,
        )

    def _require_connection(self) -> duckdb.DuckDBPyConnection:
        if self._connection is None:
            raise AnalyticalError("Соединение analytical DuckDB уже закрыто")
        return self._connection

    def _rollback_quietly(self) -> None:
        if self._connection is not None:
            with suppress(duckdb.Error):
                self._connection.execute("ROLLBACK")
