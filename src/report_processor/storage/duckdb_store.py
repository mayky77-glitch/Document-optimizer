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
from .schema import ROW_COLUMNS as _ROW_COLUMNS
from .schema import application_tables, create_database_schema, validate_existing_database
from .serialization import canonical_row_from_payload, canonical_row_payload, deterministic_json

MAX_QUERY_LIMIT = 10_000

_UPDATE_ASSIGNMENTS = ", ".join(f"{name} = excluded.{name}" for name in _ROW_COLUMNS[1:])
_UPSERT_SQL = (
    f"INSERT INTO canonical_rows ({', '.join(_ROW_COLUMNS)}) "
    f"VALUES ({', '.join('?' for _ in _ROW_COLUMNS)}) "
    f"ON CONFLICT (row_id) DO UPDATE SET {_UPDATE_ASSIGNMENTS}"
)
_ALL_ROWS_SQL = "SELECT payload_json FROM canonical_rows ORDER BY row_id ASC"


class DuckDBStore:
    """Primary canonical-row store; use a context manager or call :meth:`close`."""

    def __init__(
        self,
        database_path: Path | str,
        *,
        create_parent: bool = True,
        read_only: bool = False,
    ) -> None:
        self.database_path = Path(database_path)
        self._connection: duckdb.DuckDBPyConnection | None = None
        self._open(create_parent=create_parent, read_only=read_only)

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

    def iter_all_rows(self) -> Iterator[CanonicalSourceRow]:
        """Iterate every canonical row in stable order for downstream pipeline stages."""
        yield from self._iter_rows_from_sql(_ALL_ROWS_SQL, [])

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
            rows = self.iter_all_rows() if query is None else self.iter_rows(query)
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
                raise StorageError(f"Не удалось подготовить каталог БД {parent}: {exc}") from exc
        try:
            self._connection = duckdb.connect(str(self.database_path), read_only=read_only)
        except duckdb.Error as exc:
            raise StorageError(f"Не удалось открыть DuckDB {self.database_path}: {exc}") from exc
        try:
            if read_only:
                validate_existing_database(self._require_connection())
            else:
                self._migrate()
        except Exception:
            self.close()
            raise

    def _migrate(self) -> None:
        connection = self._require_connection()
        try:
            connection.execute("BEGIN TRANSACTION")
            existing_tables = application_tables(connection)
            if existing_tables and "storage_metadata" not in existing_tables:
                raise StorageSchemaError(
                    "БД содержит таблицы без metadata schema_version; "
                    "миграция не может быть определена"
                )
            if not existing_tables:
                create_database_schema(connection)
            else:
                validate_existing_database(connection, existing_tables)
            connection.execute("COMMIT")
        except StorageError:
            self._rollback_quietly()
            raise
        except duckdb.Error as exc:
            self._rollback_quietly()
            raise StorageMigrationError(f"Не удалось применить схему DuckDB: {exc}") from exc

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
