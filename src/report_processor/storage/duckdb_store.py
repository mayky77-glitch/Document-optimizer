from __future__ import annotations

import hashlib
from collections.abc import Iterable, Iterator
from contextlib import suppress
from pathlib import Path
from typing import Any

import duckdb

from report_processor.extraction.models import CanonicalSourceRow
from report_processor.extraction.serialization import save_rows_jsonl

from .exceptions import (
    StorageError,
    StorageExportError,
    StorageMigrationError,
    StorageQueryError,
    StorageSchemaError,
    StorageWriteError,
)
from .models import StorageExportResult, StorageQuery, StorageWriteResult
from .serialization import canonical_row_from_payload, canonical_row_payload, deterministic_json

SCHEMA_VERSION = 1
MAX_QUERY_LIMIT = 10_000

_ROW_COLUMNS = (
    *("row_id", "payload_hash", "source_type", "source_file_id"),
    *("filename", "sheet_name", "sheet_type", "source_row_number"),
    *("source_column_number", "source_column_letter", "source_coordinate", "document_index"),
    *("document_period", "object_code_raw", "object_name_raw", "subobject_code_raw"),
    *("subobject_name_raw", "position_code_raw", "work_name_raw", "unit_raw"),
    *("contract_quantity", "current_period_quantity", "cumulative_quantity", "remaining_quantity"),
    *("unit_price", "contract_cost", "current_period_cost", "cumulative_cost"),
    *("total_cost", "basis_code_raw", "drawing_code_raw", "cost_type_code_raw"),
    *("source_values_json", "warnings_json", "status", "payload_json"),
)
_NOT_NULL_COLUMNS = frozenset(
    {
        "row_id",
        "payload_hash",
        "source_type",
        "source_file_id",
        "filename",
        "sheet_name",
        "sheet_type",
        "source_row_number",
        "source_values_json",
        "warnings_json",
        "status",
        "payload_json",
    }
)
_BIGINT_COLUMNS = frozenset(("source_row_number", "source_column_number"))
_COLUMN_SPEC = tuple(
    (name, "BIGINT" if name in _BIGINT_COLUMNS else "VARCHAR", name not in _NOT_NULL_COLUMNS)
    for name in _ROW_COLUMNS
)
_FILTER_INDEXES = {
    "canonical_rows_source_file_id": "[source_file_id]",
    "canonical_rows_document_index": "[document_index]",
    "canonical_rows_document_period": "[document_period]",
    "canonical_rows_source_type": "[source_type]",
}
_METADATA_COLUMN_SPEC = (
    ("metadata_key", "VARCHAR", False),
    ("metadata_value", "VARCHAR", False),
)
_UPDATE_ASSIGNMENTS = ", ".join(f"{name} = excluded.{name}" for name in _ROW_COLUMNS[1:])
_UPSERT_SQL = (
    f"INSERT INTO canonical_rows ({', '.join(_ROW_COLUMNS)}) "
    f"VALUES ({', '.join('?' for _ in _ROW_COLUMNS)}) "
    f"ON CONFLICT (row_id) DO UPDATE SET {_UPDATE_ASSIGNMENTS}"
)
_ALL_ROWS_SQL = "SELECT payload_json FROM canonical_rows ORDER BY row_id ASC"


class DuckDBStore:
    """Primary canonical-row store; use a context manager or call :meth:`close`."""

    def __init__(self, database_path: Path | str, *, create_parent: bool = True) -> None:
        self.database_path = Path(database_path)
        self._connection: duckdb.DuckDBPyConnection | None = None
        self._open(create_parent=create_parent)

    def __enter__(self) -> DuckDBStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def write_rows(self, rows: Iterable[CanonicalSourceRow]) -> StorageWriteResult:
        """Insert or update one complete iterable in a single transaction."""
        prepared, received_count, duplicate_identical_count = self._prepare_rows(rows)
        connection = self._require_connection()
        try:
            connection.execute("BEGIN TRANSACTION")
            existing_hashes = self._existing_hashes(prepared)
            inserted_count = sum(row_id not in existing_hashes for row_id in prepared)
            existing_unchanged_count = sum(
                row_id in existing_hashes and existing_hashes[row_id] == values[1]
                for row_id, values in prepared.items()
            )
            changed_values = [
                values
                for row_id, values in prepared.items()
                if existing_hashes.get(row_id) != values[1]
            ]
            if changed_values:
                connection.executemany(_UPSERT_SQL, changed_values)
            connection.execute("COMMIT")
        except duckdb.Error as exc:
            self._rollback_quietly()
            raise StorageWriteError(f"Не удалось атомарно сохранить строки: {exc}") from exc
        except StorageError:
            self._rollback_quietly()
            raise
        except Exception as exc:
            self._rollback_quietly()
            raise StorageWriteError(f"Не удалось подготовить строки для сохранения: {exc}") from exc

        unchanged_count = existing_unchanged_count + duplicate_identical_count
        return StorageWriteResult(
            database_path=self.database_path,
            received_count=received_count,
            inserted_count=inserted_count,
            updated_count=received_count - inserted_count - unchanged_count,
            unchanged_count=unchanged_count,
        )

    def get_row(self, row_id: str) -> CanonicalSourceRow | None:
        if not row_id:
            raise StorageQueryError("row_id не может быть пустым")
        try:
            record = (
                self._require_connection()
                .execute("SELECT payload_json FROM canonical_rows WHERE row_id = ?", [row_id])
                .fetchone()
            )
            return canonical_row_from_payload(record[0]) if record is not None else None
        except StorageError:
            raise
        except duckdb.Error as exc:
            raise StorageQueryError(f"Не удалось получить строку {row_id!r}: {exc}") from exc

    def iter_rows(self, query: StorageQuery | None = None) -> Iterator[CanonicalSourceRow]:
        sql, parameters = self._query_sql(query)
        yield from self._iter_rows_from_sql(sql, parameters)

    def _iter_rows_from_sql(self, sql: str, params: list[Any]) -> Iterator[CanonicalSourceRow]:
        try:
            records = self._require_connection().execute(sql, params).fetchall()
            for record in records:
                yield canonical_row_from_payload(record[0])
        except StorageError:
            raise
        except duckdb.Error as exc:
            raise StorageQueryError(f"Не удалось запросить сохранённые строки: {exc}") from exc

    def export_jsonl(
        self,
        output_path: Path | str,
        query: StorageQuery | None = None,
    ) -> StorageExportResult:
        try:
            rows = (
                self._iter_rows_from_sql(_ALL_ROWS_SQL, [])
                if query is None
                else self.iter_rows(query)
            )
            exported = save_rows_jsonl(rows, Path(output_path))
        except StorageError:
            raise
        except Exception as exc:
            raise StorageExportError(f"Не удалось экспортировать JSONL: {exc}") from exc
        return StorageExportResult(
            output_path=exported.output_path,
            meta_path=exported.meta_path,
            row_count=exported.row_count,
            bytes_written=exported.bytes_written,
        )

    def _open(self, *, create_parent: bool) -> None:
        if self.database_path != Path(":memory:"):
            parent = self.database_path.parent
            try:
                if create_parent:
                    parent.mkdir(parents=True, exist_ok=True)
                elif not parent.is_dir():
                    raise FileNotFoundError(parent)
            except OSError as exc:
                raise StorageError(f"Не удалось подготовить каталог БД {parent}: {exc}") from exc
        try:
            self._connection = duckdb.connect(str(self.database_path))
        except duckdb.Error as exc:
            raise StorageError(f"Не удалось открыть DuckDB {self.database_path}: {exc}") from exc
        try:
            self._migrate()
        except Exception:
            self.close()
            raise

    def _migrate(self) -> None:
        connection = self._require_connection()
        try:
            connection.execute("BEGIN TRANSACTION")
            existing_tables = _application_tables(connection)
            if existing_tables and "storage_metadata" not in existing_tables:
                raise StorageSchemaError(
                    "БД содержит таблицы без metadata schema_version; "
                    "миграция не может быть определена"
                )
            if not existing_tables:
                self._create_metadata_schema(connection)
                self._create_schema(connection)
                connection.execute(
                    "INSERT INTO storage_metadata (metadata_key, metadata_value) VALUES (?, ?)",
                    ["schema_version", str(SCHEMA_VERSION)],
                )
            else:
                self._validate_metadata_schema(connection)
                version = _schema_version(self._schema_version_value(connection))
                if version > SCHEMA_VERSION:
                    raise StorageSchemaError(
                        f"Версия схемы {version} новее поддерживаемой {SCHEMA_VERSION}"
                    )
                if version != SCHEMA_VERSION:
                    raise StorageMigrationError(f"Не поддерживается миграция схемы {version}")
                self._validate_schema(connection)
            connection.execute("COMMIT")
        except StorageError:
            self._rollback_quietly()
            raise
        except duckdb.Error as exc:
            self._rollback_quietly()
            raise StorageMigrationError(f"Не удалось применить схему DuckDB: {exc}") from exc

    @staticmethod
    def _create_metadata_schema(connection: duckdb.DuckDBPyConnection) -> None:
        connection.execute(
            "CREATE TABLE storage_metadata "
            "(metadata_key VARCHAR PRIMARY KEY, metadata_value VARCHAR NOT NULL)"
        )

    @staticmethod
    def _create_schema(connection: duckdb.DuckDBPyConnection) -> None:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS canonical_rows ("
            "row_id VARCHAR PRIMARY KEY, payload_hash VARCHAR NOT NULL, "
            "source_type VARCHAR NOT NULL, source_file_id VARCHAR NOT NULL, "
            "filename VARCHAR NOT NULL, sheet_name VARCHAR NOT NULL, "
            "sheet_type VARCHAR NOT NULL, source_row_number BIGINT NOT NULL, "
            "source_column_number BIGINT, "
            "source_column_letter VARCHAR, source_coordinate VARCHAR, document_index VARCHAR, "
            "document_period VARCHAR, object_code_raw VARCHAR, object_name_raw VARCHAR, "
            "subobject_code_raw VARCHAR, subobject_name_raw VARCHAR, position_code_raw VARCHAR, "
            "work_name_raw VARCHAR, unit_raw VARCHAR, contract_quantity VARCHAR, "
            "current_period_quantity VARCHAR, cumulative_quantity VARCHAR, "
            "remaining_quantity VARCHAR, "
            "unit_price VARCHAR, contract_cost VARCHAR, current_period_cost VARCHAR, "
            "cumulative_cost VARCHAR, total_cost VARCHAR, basis_code_raw VARCHAR, "
            "drawing_code_raw VARCHAR, cost_type_code_raw VARCHAR, "
            "source_values_json VARCHAR NOT NULL, warnings_json VARCHAR NOT NULL, "
            "status VARCHAR NOT NULL, payload_json VARCHAR NOT NULL)"
        )
        for name, column in (
            ("canonical_rows_source_file_id", "source_file_id"),
            ("canonical_rows_document_index", "document_index"),
            ("canonical_rows_document_period", "document_period"),
            ("canonical_rows_source_type", "source_type"),
        ):
            connection.execute(f"CREATE INDEX IF NOT EXISTS {name} ON canonical_rows ({column})")

    @staticmethod
    def _validate_metadata_schema(connection: duckdb.DuckDBPyConnection) -> None:
        _validate_table_columns(connection, "storage_metadata", _METADATA_COLUMN_SPEC)
        primary_keys = connection.execute(
            "SELECT constraint_column_names FROM duckdb_constraints() "
            "WHERE table_name = 'storage_metadata' AND constraint_type = 'PRIMARY KEY'"
        ).fetchall()
        if primary_keys != [(["metadata_key"],)]:
            raise StorageSchemaError("В таблице storage_metadata нужен PRIMARY KEY (metadata_key)")

    @staticmethod
    def _schema_version_value(connection: duckdb.DuckDBPyConnection) -> str:
        records = connection.execute(
            "SELECT metadata_value FROM storage_metadata WHERE metadata_key = 'schema_version'"
        ).fetchall()
        if len(records) != 1:
            raise StorageSchemaError(
                "В storage_metadata должна быть ровно одна запись schema_version"
            )
        return records[0][0]

    @staticmethod
    def _validate_schema(connection: duckdb.DuckDBPyConnection) -> None:
        table = connection.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'main' AND table_name = 'canonical_rows'"
        ).fetchone()
        if table is None:
            raise StorageSchemaError("В схеме версии 1 отсутствует таблица canonical_rows")
        _validate_table_columns(connection, "canonical_rows", _COLUMN_SPEC)
        primary_keys = connection.execute(
            "SELECT constraint_column_names FROM duckdb_constraints() "
            "WHERE table_name = 'canonical_rows' AND constraint_type = 'PRIMARY KEY'"
        ).fetchall()
        if primary_keys != [(["row_id"],)]:
            raise StorageSchemaError("В таблице canonical_rows нужен PRIMARY KEY (row_id)")
        indexes = {
            index_name: expression
            for index_name, expression in connection.execute(
                "SELECT index_name, expressions FROM duckdb_indexes() "
                "WHERE schema_name = 'main' AND table_name = 'canonical_rows'"
            ).fetchall()
        }
        if not all(indexes.get(name) == expression for name, expression in _FILTER_INDEXES.items()):
            raise StorageSchemaError(
                "В таблице canonical_rows отсутствуют обязательные filter indexes"
            )

    def _prepare_rows(
        self,
        rows: Iterable[CanonicalSourceRow],
    ) -> tuple[dict[str, tuple[Any, ...]], int, int]:
        prepared: dict[str, tuple[Any, ...]] = {}
        received_count = 0
        duplicate_identical_count = 0
        try:
            for row in rows:
                received_count += 1
                if not isinstance(row, CanonicalSourceRow):
                    raise TypeError("ожидался CanonicalSourceRow")
                if not row.row_id:
                    raise ValueError("row_id не может быть пустым")
                values = _row_values(row)
                previous = prepared.get(row.row_id)
                if previous is not None:
                    if previous[1] != values[1]:
                        raise ValueError(f"повторный row_id {row.row_id!r} содержит разные данные")
                    duplicate_identical_count += 1
                    continue
                prepared[row.row_id] = values
        except (TypeError, ValueError) as exc:
            raise StorageWriteError(f"Некорректная каноническая строка: {exc}") from exc
        return dict(sorted(prepared.items())), received_count, duplicate_identical_count

    def _existing_hashes(self, prepared: dict[str, tuple[Any, ...]]) -> dict[str, str]:
        if not prepared:
            return {}
        placeholders = ", ".join("?" for _ in prepared)
        records = (
            self._require_connection()
            .execute(
                f"SELECT row_id, payload_hash FROM canonical_rows WHERE row_id IN ({placeholders})",
                list(prepared),
            )
            .fetchall()
        )
        return {row_id: value_hash for row_id, value_hash in records}

    def _query_sql(self, query: StorageQuery | None) -> tuple[str, list[Any]]:
        query = query or StorageQuery()
        if not isinstance(query, StorageQuery):
            raise StorageQueryError("query должен быть StorageQuery или None")
        if query.limit is None or not isinstance(query.limit, int) or isinstance(query.limit, bool):
            raise StorageQueryError("limit должен быть целым числом от 1 до 10000")
        if not 1 <= query.limit <= MAX_QUERY_LIMIT:
            raise StorageQueryError(f"limit должен быть от 1 до {MAX_QUERY_LIMIT}")
        clauses: list[str] = []
        parameters: list[Any] = []
        for column, value in (
            ("source_file_id", query.source_file_id),
            ("document_index", query.document_index),
            ("document_period", query.document_period),
            ("source_type", query.source_type),
        ):
            if value is not None:
                if not isinstance(value, str):
                    raise StorageQueryError(f"Фильтр {column} должен быть строкой")
                clauses.append(f"{column} = ?")
                parameters.append(value)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        parameters.append(query.limit)
        sql = f"SELECT payload_json FROM canonical_rows{where} ORDER BY row_id ASC LIMIT ?"
        return sql, parameters

    def _require_connection(self) -> duckdb.DuckDBPyConnection:
        if self._connection is None:
            raise StorageError("Соединение DuckDB уже закрыто")
        return self._connection

    def _rollback_quietly(self) -> None:
        if self._connection is not None:
            with suppress(duckdb.Error):
                self._connection.execute("ROLLBACK")


def _schema_version(value: Any) -> int:
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
        raise StorageSchemaError("schema_version должен быть неотрицательным целым числом")
    return int(value)


def _application_tables(connection: duckdb.DuckDBPyConnection) -> set[str]:
    records = connection.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_type = 'BASE TABLE'"
    ).fetchall()
    return {record[0] for record in records}


def _validate_table_columns(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
    expected_spec: tuple[tuple[str, str, bool], ...],
) -> None:
    actual = {
        row[0]: (row[1], row[2] == "YES")
        for row in connection.execute(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_schema = 'main' AND table_name = ?",
            [table_name],
        ).fetchall()
    }
    expected = {name: (data_type, nullable) for name, data_type, nullable in expected_spec}
    if actual == expected:
        return
    missing = set(expected) - set(actual)
    unexpected = set(actual) - set(expected)
    mismatched = sorted(
        name for name in set(actual) & set(expected) if actual[name] != expected[name]
    )
    details = []
    if missing:
        details.append(f"отсутствуют: {', '.join(sorted(missing))}")
    if unexpected:
        details.append(f"лишние: {', '.join(sorted(unexpected))}")
    if mismatched:
        details.append(f"неверные типы/nullability: {', '.join(mismatched)}")
    raise StorageSchemaError(
        f"Таблица {table_name} не соответствует схеме v1 (" + "; ".join(details) + ")"
    )


def _row_values(row: CanonicalSourceRow) -> tuple[Any, ...]:
    payload = canonical_row_payload(row)
    payload_json = deterministic_json(payload)
    location = row.source_location
    return (
        row.row_id,
        hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        row.source_type,
        location.source_file_id,
        location.filename,
        location.sheet_name,
        location.sheet_type,
        location.row_number,
        location.column_number,
        location.column_letter,
        location.coordinate,
        row.document_index,
        row.document_period,
        row.object_code_raw,
        row.object_name_raw,
        row.subobject_code_raw,
        row.subobject_name_raw,
        row.position_code_raw,
        row.work_name_raw,
        row.unit_raw,
        _decimal_text(row.contract_quantity),
        _decimal_text(row.current_period_quantity),
        _decimal_text(row.cumulative_quantity),
        _decimal_text(row.remaining_quantity),
        _decimal_text(row.unit_price),
        _decimal_text(row.contract_cost),
        _decimal_text(row.current_period_cost),
        _decimal_text(row.cumulative_cost),
        _decimal_text(row.total_cost),
        row.basis_code_raw,
        row.drawing_code_raw,
        row.cost_type_code_raw,
        deterministic_json(payload["source_values"]),
        deterministic_json(payload["warnings"]),
        row.status,
        payload_json,
    )


def _decimal_text(value: object) -> str | None:
    return str(value) if value is not None else None
