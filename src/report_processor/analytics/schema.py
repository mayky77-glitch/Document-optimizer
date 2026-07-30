"""Fixed AnalyticalSchema-1 DDL and defensive schema validation."""

from __future__ import annotations

from typing import Final

import duckdb

from .exceptions import AnalyticalMigrationError, AnalyticalSchemaError
from .models import ANALYTICAL_SCHEMA_VERSION

_DECIMAL = "DECIMAL(38,18)"
_TABLE_COLUMNS: Final[dict[str, tuple[tuple[str, str, bool], ...]]] = {
    "analytical_metadata": (
        ("metadata_key", "VARCHAR", False),
        ("metadata_value", "VARCHAR", False),
    ),
    "source_rows": (
        ("source_row_id", "VARCHAR", False),
        ("payload_hash", "VARCHAR", False),
        ("line_id", "VARCHAR", False),
        ("source_file_id", "VARCHAR", False),
        ("source_filename", "VARCHAR", False),
        ("source_sheet", "VARCHAR", False),
        ("source_row_number", "BIGINT", False),
        ("document_type", "VARCHAR", False),
        ("document_period", "VARCHAR", True),
        ("object_code", "VARCHAR", True),
        ("subobject_code", "VARCHAR", True),
        ("position_code", "VARCHAR", True),
        ("cost_type_code", "VARCHAR", True),
        ("drawing_code", "VARCHAR", True),
        ("basis_code", "VARCHAR", True),
        ("work_name", "VARCHAR", True),
        ("unit", "VARCHAR", True),
        ("work_name_tokens_json", "VARCHAR", False),
        ("code_tokens_json", "VARCHAR", False),
        ("unit_tokens_json", "VARCHAR", False),
        ("contract_quantity", _DECIMAL, True),
        ("period_quantity", _DECIMAL, True),
        ("cumulative_quantity", _DECIMAL, True),
        ("remaining_quantity", _DECIMAL, True),
        ("unit_price", _DECIMAL, True),
        ("contract_cost", _DECIMAL, True),
        ("period_cost", _DECIMAL, True),
        ("cumulative_cost", _DECIMAL, True),
        ("total_cost", _DECIMAL, True),
        ("is_detail", "BOOLEAN", False),
        ("is_total", "BOOLEAN", False),
        ("is_outdated", "BOOLEAN", False),
        ("formula_error", "VARCHAR", False),
        ("data_quality_status", "VARCHAR", False),
        ("warnings_json", "VARCHAR", False),
        ("payload_json", "VARCHAR", False),
    ),
    "target_rows": (
        ("target_row_id", "VARCHAR", False),
        ("payload_hash", "VARCHAR", False),
        ("target_source_id", "VARCHAR", False),
        ("target_fingerprint", "VARCHAR", False),
        ("sheet_name", "VARCHAR", False),
        ("sheet_type", "VARCHAR", False),
        ("row_number", "BIGINT", False),
        ("object_code", "VARCHAR", True),
        ("object_name", "VARCHAR", True),
        ("subobject_code", "VARCHAR", True),
        ("subobject_name", "VARCHAR", True),
        ("position_code", "VARCHAR", True),
        ("work_name", "VARCHAR", True),
        ("unit", "VARCHAR", True),
        ("row_kind", "VARCHAR", False),
        ("scope", "VARCHAR", False),
        ("stage", "VARCHAR", True),
        ("document_index_raw", "VARCHAR", True),
        ("document_index_normalized", "VARCHAR", True),
        ("document_quantity", _DECIMAL, True),
        ("selected_quantity", _DECIMAL, True),
        ("document_cost", _DECIMAL, True),
        ("selected_cost", _DECIMAL, True),
        ("writable", "BOOLEAN", False),
        ("status", "VARCHAR", False),
        ("warnings_json", "VARCHAR", False),
        ("payload_json", "VARCHAR", False),
    ),
    "rule_sets": (
        ("content_hash", "VARCHAR", False),
        ("configuration_version", "VARCHAR", False),
        ("rule_set_version", "VARCHAR", False),
        ("defaults_json", "VARCHAR", False),
        ("canonical_json", "VARCHAR", False),
        ("payload_hash", "VARCHAR", False),
    ),
    "rule_clauses": (
        ("content_hash", "VARCHAR", False),
        ("rule_id", "VARCHAR", False),
        ("clause_index", "BIGINT", False),
        ("rule_version", "VARCHAR", False),
        ("rule_priority", "BIGINT", False),
        ("rule_status", "VARCHAR", False),
        ("rule_origin", "VARCHAR", False),
        ("scope_json", "VARCHAR", False),
        ("action", "VARCHAR", False),
        ("match_kind", "VARCHAR", False),
        ("field", "VARCHAR", False),
        ("literal", "VARCHAR", False),
        ("priority", "BIGINT", False),
        ("hard_exclude", "BOOLEAN", False),
        ("required_substrings_json", "VARCHAR", False),
        ("forbidden_substrings_json", "VARCHAR", False),
        ("source_units_json", "VARCHAR", False),
        ("excluded_units_json", "VARCHAR", False),
        ("include_quantity", "BOOLEAN", False),
        ("include_cost", "BOOLEAN", False),
        ("payload_json", "VARCHAR", False),
    ),
    "warnings": (
        ("entity_type", "VARCHAR", False),
        ("entity_id", "VARCHAR", False),
        ("warning_index", "BIGINT", False),
        ("warning", "VARCHAR", False),
        ("provenance_json", "VARCHAR", False),
    ),
}
_PRIMARY_KEYS: Final = {
    "analytical_metadata": ("metadata_key",),
    "source_rows": ("source_row_id",),
    "target_rows": ("target_row_id",),
    "rule_sets": ("content_hash",),
    "rule_clauses": ("content_hash", "rule_id", "clause_index"),
    "warnings": ("entity_type", "entity_id", "warning_index"),
}
_INDEXES: Final = {
    "source_rows_line_id": "[line_id]",
    "target_rows_source_fingerprint": "[target_source_id, target_fingerprint]",
    "warnings_entity": "[entity_type, entity_id]",
}
_VIEW_SQL: Final = {
    "v_source_rows": "CREATE VIEW v_source_rows AS SELECT * FROM source_rows",
    "v_target_rows": "CREATE VIEW v_target_rows AS SELECT * FROM target_rows",
    "v_rule_clauses": "CREATE VIEW v_rule_clauses AS SELECT * FROM rule_clauses",
    "v_diagnostics": (
        "CREATE VIEW v_diagnostics AS "
        "SELECT entity_type, entity_id, warning_index, warning, provenance_json FROM warnings"
    ),
}


def application_tables(connection: duckdb.DuckDBPyConnection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' AND table_type = 'BASE TABLE'"
        ).fetchall()
    }


def create_database_schema(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        "CREATE TABLE analytical_metadata "
        "(metadata_key VARCHAR PRIMARY KEY, metadata_value VARCHAR NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE source_rows ("
        + ", ".join(_column_ddl(spec) for spec in _TABLE_COLUMNS["source_rows"])
        + ", PRIMARY KEY (source_row_id))"
    )
    connection.execute(
        "CREATE TABLE target_rows ("
        + ", ".join(_column_ddl(spec) for spec in _TABLE_COLUMNS["target_rows"])
        + ", PRIMARY KEY (target_row_id))"
    )
    connection.execute(
        "CREATE TABLE rule_sets ("
        + ", ".join(_column_ddl(spec) for spec in _TABLE_COLUMNS["rule_sets"])
        + ", PRIMARY KEY (content_hash))"
    )
    connection.execute(
        "CREATE TABLE rule_clauses ("
        + ", ".join(_column_ddl(spec) for spec in _TABLE_COLUMNS["rule_clauses"])
        + ", PRIMARY KEY (content_hash, rule_id, clause_index))"
    )
    connection.execute(
        "CREATE TABLE warnings ("
        + ", ".join(_column_ddl(spec) for spec in _TABLE_COLUMNS["warnings"])
        + ", PRIMARY KEY (entity_type, entity_id, warning_index))"
    )
    connection.execute("CREATE INDEX source_rows_line_id ON source_rows (line_id)")
    connection.execute(
        "CREATE INDEX target_rows_source_fingerprint "
        "ON target_rows (target_source_id, target_fingerprint)"
    )
    connection.execute("CREATE INDEX warnings_entity ON warnings (entity_type, entity_id)")
    for statement in _VIEW_SQL.values():
        connection.execute(statement)
    connection.execute(
        "INSERT INTO analytical_metadata VALUES (?, ?)",
        ["schema_version", ANALYTICAL_SCHEMA_VERSION],
    )


def validate_existing_database(connection: duckdb.DuckDBPyConnection) -> None:
    tables = application_tables(connection)
    expected_tables = set(_TABLE_COLUMNS)
    if not tables:
        raise AnalyticalMigrationError("Пустая схема должна создаваться транзакционно")
    if tables != expected_tables:
        raise AnalyticalSchemaError("Набор таблиц не соответствует AnalyticalSchema-1")
    _validate_metadata(connection)
    for table, columns in _TABLE_COLUMNS.items():
        _validate_columns(connection, table, columns)
        _validate_primary_key(connection, table, _PRIMARY_KEYS[table])
    actual_indexes = {
        row[0]: row[1]
        for row in connection.execute(
            "SELECT index_name, expressions FROM duckdb_indexes() WHERE schema_name = 'main'"
        ).fetchall()
    }
    if any(actual_indexes.get(name) != expression for name, expression in _INDEXES.items()):
        raise AnalyticalSchemaError("Отсутствуют обязательные analytical indexes")
    views = {
        row[0]: row[1]
        for row in connection.execute(
            "SELECT view_name, sql FROM duckdb_views() WHERE schema_name = 'main' AND NOT internal"
        ).fetchall()
    }
    if set(views) != set(_VIEW_SQL) or any(
        _normalized_sql(views[name]) != _normalized_sql(statement)
        for name, statement in _VIEW_SQL.items()
    ):
        raise AnalyticalSchemaError("Analytical views не соответствуют AnalyticalSchema-1")


def _column_ddl(spec: tuple[str, str, bool]) -> str:
    name, data_type, nullable = spec
    return f"{name} {data_type}{'' if nullable else ' NOT NULL'}"


def _validate_metadata(connection: duckdb.DuckDBPyConnection) -> None:
    rows = connection.execute(
        "SELECT metadata_value FROM analytical_metadata WHERE metadata_key = 'schema_version'"
    ).fetchall()
    if len(rows) != 1 or not isinstance(rows[0][0], str):
        raise AnalyticalSchemaError("analytical_metadata должна содержать schema_version")
    version = rows[0][0]
    current = _schema_number(ANALYTICAL_SCHEMA_VERSION)
    candidate = _schema_number(version)
    if candidate is not None and candidate > current:
        raise AnalyticalSchemaError(f"Версия схемы {version} новее {ANALYTICAL_SCHEMA_VERSION}")
    if version != ANALYTICAL_SCHEMA_VERSION:
        raise AnalyticalMigrationError(f"Миграция схемы {version} не поддерживается")


def _schema_number(value: str) -> int | None:
    prefix = "AnalyticalSchema-"
    suffix = value.removeprefix(prefix)
    return int(suffix) if suffix != value and suffix.isdecimal() else None


def _validate_columns(
    connection: duckdb.DuckDBPyConnection, table: str, expected: tuple[tuple[str, str, bool], ...]
) -> None:
    actual = {
        row[0]: (row[1], row[2] == "YES")
        for row in connection.execute(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_schema = 'main' AND table_name = ?",
            [table],
        ).fetchall()
    }
    required = {name: (data_type, nullable) for name, data_type, nullable in expected}
    if actual != required:
        raise AnalyticalSchemaError(f"Таблица {table} не соответствует AnalyticalSchema-1")


def _validate_primary_key(
    connection: duckdb.DuckDBPyConnection, table: str, expected: tuple[str, ...]
) -> None:
    rows = connection.execute(
        "SELECT constraint_column_names FROM duckdb_constraints() "
        "WHERE table_name = ? AND constraint_type = 'PRIMARY KEY'",
        [table],
    ).fetchall()
    if rows != [(list(expected),)]:
        raise AnalyticalSchemaError(f"Таблица {table} имеет неверный primary key")


def _normalized_sql(value: str) -> str:
    return " ".join(value.removesuffix(";").split()).casefold()
