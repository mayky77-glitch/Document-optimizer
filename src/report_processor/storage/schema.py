from __future__ import annotations

from typing import Any

import duckdb

from .exceptions import StorageMigrationError, StorageSchemaError

SCHEMA_VERSION = 1

ROW_COLUMNS = (
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
COLUMN_SPEC = tuple(
    (name, "BIGINT" if name in _BIGINT_COLUMNS else "VARCHAR", name not in _NOT_NULL_COLUMNS)
    for name in ROW_COLUMNS
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


def application_tables(connection: duckdb.DuckDBPyConnection) -> set[str]:
    records = connection.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_type = 'BASE TABLE'"
    ).fetchall()
    return {record[0] for record in records}


def create_database_schema(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        "CREATE TABLE storage_metadata "
        "(metadata_key VARCHAR PRIMARY KEY, metadata_value VARCHAR NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE canonical_rows ("
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
        "remaining_quantity VARCHAR, unit_price VARCHAR, contract_cost VARCHAR, "
        "current_period_cost VARCHAR, cumulative_cost VARCHAR, total_cost VARCHAR, "
        "basis_code_raw VARCHAR, drawing_code_raw VARCHAR, cost_type_code_raw VARCHAR, "
        "source_values_json VARCHAR NOT NULL, warnings_json VARCHAR NOT NULL, "
        "status VARCHAR NOT NULL, payload_json VARCHAR NOT NULL)"
    )
    for name, column in (
        ("canonical_rows_source_file_id", "source_file_id"),
        ("canonical_rows_document_index", "document_index"),
        ("canonical_rows_document_period", "document_period"),
        ("canonical_rows_source_type", "source_type"),
    ):
        connection.execute(f"CREATE INDEX {name} ON canonical_rows ({column})")
    connection.execute(
        "INSERT INTO storage_metadata (metadata_key, metadata_value) VALUES (?, ?)",
        ["schema_version", str(SCHEMA_VERSION)],
    )


def validate_existing_database(
    connection: duckdb.DuckDBPyConnection,
    existing_tables: set[str] | None = None,
) -> None:
    tables = existing_tables if existing_tables is not None else application_tables(connection)
    if "storage_metadata" not in tables:
        raise StorageSchemaError(
            "БД не содержит metadata schema_version; миграция не может быть определена"
        )
    _validate_metadata_schema(connection)
    version = _schema_version(_schema_version_value(connection))
    if version > SCHEMA_VERSION:
        raise StorageSchemaError(f"Версия схемы {version} новее поддерживаемой {SCHEMA_VERSION}")
    if version != SCHEMA_VERSION:
        raise StorageMigrationError(f"Не поддерживается миграция схемы {version}")
    _validate_canonical_schema(connection)


def _validate_metadata_schema(connection: duckdb.DuckDBPyConnection) -> None:
    _validate_table_columns(connection, "storage_metadata", _METADATA_COLUMN_SPEC)
    primary_keys = connection.execute(
        "SELECT constraint_column_names FROM duckdb_constraints() "
        "WHERE table_name = 'storage_metadata' AND constraint_type = 'PRIMARY KEY'"
    ).fetchall()
    if primary_keys != [(["metadata_key"],)]:
        raise StorageSchemaError("В таблице storage_metadata нужен PRIMARY KEY (metadata_key)")


def _schema_version_value(connection: duckdb.DuckDBPyConnection) -> str:
    records = connection.execute(
        "SELECT metadata_value FROM storage_metadata WHERE metadata_key = 'schema_version'"
    ).fetchall()
    if len(records) != 1:
        raise StorageSchemaError(
            "В storage_metadata должна быть ровно одна запись schema_version"
        )
    return records[0][0]


def _schema_version(value: Any) -> int:
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
        raise StorageSchemaError("schema_version должен быть неотрицательным целым числом")
    return int(value)


def _validate_canonical_schema(connection: duckdb.DuckDBPyConnection) -> None:
    table = connection.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_name = 'canonical_rows'"
    ).fetchone()
    if table is None:
        raise StorageSchemaError("В схеме версии 1 отсутствует таблица canonical_rows")
    _validate_table_columns(connection, "canonical_rows", COLUMN_SPEC)
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
        raise StorageSchemaError("В таблице canonical_rows отсутствуют обязательные filter indexes")


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
