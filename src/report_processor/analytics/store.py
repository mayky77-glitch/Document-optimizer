"""Transactional DuckDB implementation of the isolated analytical store."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable, Mapping
from contextlib import suppress
from dataclasses import asdict
from hashlib import sha256
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
from .models import (
    ANALYTICAL_SCHEMA_VERSION,
    MAX_QUERY_LIMIT,
    AnalyticalExportResult,
    AnalyticalLoadResult,
    AnalyticalQuery,
    AnalyticalQueryResult,
)
from .schema import application_tables, create_database_schema, validate_existing_database
from .serialization import deterministic_json, payload_hash, strict_decimal, target_row_id

_SOURCE_COLUMNS = (
    "source_row_id",
    "payload_hash",
    "line_id",
    "source_file_id",
    "source_filename",
    "source_sheet",
    "source_row_number",
    "document_type",
    "document_period",
    "object_code",
    "subobject_code",
    "position_code",
    "cost_type_code",
    "drawing_code",
    "basis_code",
    "work_name",
    "unit",
    "work_name_tokens_json",
    "code_tokens_json",
    "unit_tokens_json",
    "contract_quantity",
    "period_quantity",
    "cumulative_quantity",
    "remaining_quantity",
    "unit_price",
    "contract_cost",
    "period_cost",
    "cumulative_cost",
    "total_cost",
    "is_detail",
    "is_total",
    "is_outdated",
    "formula_error",
    "data_quality_status",
    "warnings_json",
    "payload_json",
)
_TARGET_COLUMNS = (
    "target_row_id",
    "payload_hash",
    "target_source_id",
    "target_fingerprint",
    "sheet_name",
    "sheet_type",
    "row_number",
    "object_code",
    "object_name",
    "subobject_code",
    "subobject_name",
    "position_code",
    "work_name",
    "unit",
    "row_kind",
    "scope",
    "stage",
    "document_index_raw",
    "document_index_normalized",
    "document_quantity",
    "selected_quantity",
    "document_cost",
    "selected_cost",
    "writable",
    "status",
    "warnings_json",
    "payload_json",
)
_RULE_SET_COLUMNS = (
    "content_hash",
    "configuration_version",
    "rule_set_version",
    "defaults_json",
    "canonical_json",
    "payload_hash",
)
_RULE_CLAUSE_COLUMNS = (
    "content_hash",
    "rule_id",
    "clause_index",
    "rule_version",
    "rule_priority",
    "rule_status",
    "rule_origin",
    "scope_json",
    "action",
    "match_kind",
    "field",
    "literal",
    "priority",
    "hard_exclude",
    "required_substrings_json",
    "forbidden_substrings_json",
    "source_units_json",
    "excluded_units_json",
    "include_quantity",
    "include_cost",
    "payload_json",
)
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
        prepared, received, duplicate_count, warnings = self._prepare_source_rows(rows)
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
        prepared, received, duplicate_count, warnings = self._prepare_target_rows(
            rows, target_source_id, target_fingerprint
        )
        inserted, unchanged = self._load_rows(
            table="target_rows", key_column="target_row_id", values=prepared, warnings=warnings
        )
        return AnalyticalLoadResult(
            self.database_path, "target_rows", received, inserted, unchanged + duplicate_count
        )

    def load_rule_set(self, rule_set: ValidatedRuleSet) -> AnalyticalLoadResult:
        if not isinstance(rule_set, ValidatedRuleSet):
            raise AnalyticalWriteError("ожидался ValidatedRuleSet")
        expected_hash = sha256(rule_set.canonical_json).hexdigest()
        if rule_set.content_hash != expected_hash:
            raise AnalyticalWriteError("content_hash не соответствует canonical_json")
        canonical_json = _decode_canonical_json(rule_set.canonical_json)
        payload_json, payload_digest = payload_hash(canonical_json)
        values = (
            rule_set.content_hash,
            rule_set.configuration_version.value,
            rule_set.rule_set_version,
            deterministic_json(asdict(rule_set.defaults)),
            rule_set.canonical_json.decode("utf-8"),
            payload_digest,
        )
        clauses = _rule_clause_values(rule_set.content_hash, canonical_json, payload_json)
        try:
            connection = self._require_connection()
            connection.execute("BEGIN TRANSACTION")
            existing = self._hash_for_key("rule_sets", "content_hash", rule_set.content_hash)
            if existing is not None and existing != payload_digest:
                raise AnalyticalWriteError("content_hash уже существует с другим payload")
            if existing is None:
                self._insert_many("rule_sets", _RULE_SET_COLUMNS, [values])
                if clauses:
                    self._insert_many("rule_clauses", _RULE_CLAUSE_COLUMNS, clauses)
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
            temp_path, count, byte_count = _write_diagnostics_temp(output, records)
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

    def _prepare_source_rows(
        self, rows: Iterable[NormalizedSourceRow]
    ) -> tuple[dict[str, tuple[Any, ...]], int, int, dict[str, tuple[str, ...]]]:
        prepared: dict[str, tuple[Any, ...]] = {}
        warnings: dict[str, tuple[str, ...]] = {}
        received = duplicate_count = 0
        try:
            for row in rows:
                received += 1
                if not isinstance(row, NormalizedSourceRow) or not row.source_row_id:
                    raise TypeError("ожидался NormalizedSourceRow с source_row_id")
                payload_json, digest = payload_hash(row)
                source = row.source_row
                row_warnings = _warnings(row.warnings)
                values = (
                    row.source_row_id,
                    digest,
                    row.line_id,
                    row.source_file_id,
                    row.source_filename,
                    row.source_sheet,
                    row.source_row_number,
                    source.document_type,
                    source.document_period,
                    row.object_code,
                    row.subobject_code,
                    row.position_code,
                    row.cost_type_code,
                    row.drawing_code,
                    row.basis_code,
                    row.work_name,
                    row.unit,
                    deterministic_json(row.work_name_tokens),
                    deterministic_json(row.code_tokens),
                    deterministic_json(row.unit_tokens),
                    *[
                        strict_decimal(value, field_name=name)
                        for name, value in zip(_decimal_columns(), row.decimals, strict=True)
                    ],
                    source.is_detail,
                    source.is_total,
                    source.is_outdated,
                    source.formula_error.value,
                    source.data_quality_status.value,
                    deterministic_json(row_warnings),
                    payload_json,
                )
                duplicate_count += _add_prepared(
                    prepared, warnings, row.source_row_id, values, row_warnings
                )
        except (TypeError, ValueError) as exc:
            raise AnalyticalWriteError(f"Некорректная normalized source row: {exc}") from exc
        return dict(sorted(prepared.items())), received, duplicate_count, warnings

    def _prepare_target_rows(
        self, rows: Iterable[TargetReportRow], source_id: str, fingerprint: str
    ) -> tuple[dict[str, tuple[Any, ...]], int, int, dict[str, tuple[str, ...]]]:
        prepared: dict[str, tuple[Any, ...]] = {}
        warnings: dict[str, tuple[str, ...]] = {}
        received = duplicate_count = 0
        try:
            for row in rows:
                received += 1
                if not isinstance(row, TargetReportRow) or not row.sheet_name or row.row_number < 1:
                    raise TypeError(
                        "ожидался TargetReportRow с sheet_name и положительным row_number"
                    )
                row_id = target_row_id(source_id, fingerprint, row.sheet_name, row.row_number)
                payload_json, digest = payload_hash(row)
                row_warnings = _warnings(row.warnings)
                values = (
                    row_id,
                    digest,
                    source_id,
                    fingerprint,
                    row.sheet_name,
                    row.sheet_type.value,
                    row.row_number,
                    row.object_code,
                    row.object_name,
                    row.subobject_code,
                    row.subobject_name,
                    row.position_code,
                    row.work_name,
                    row.unit,
                    row.row_kind,
                    row.scope,
                    row.stage,
                    row.document_index_raw,
                    row.document_index_normalized,
                    strict_decimal(
                        _numeric_value(row.document_quantity), field_name="document_quantity"
                    ),
                    strict_decimal(
                        _numeric_value(row.selected_quantity), field_name="selected_quantity"
                    ),
                    strict_decimal(_numeric_value(row.document_cost), field_name="document_cost"),
                    strict_decimal(_numeric_value(row.selected_cost), field_name="selected_cost"),
                    row.writable,
                    row.status,
                    deterministic_json(row_warnings),
                    payload_json,
                )
                duplicate_count += _add_prepared(prepared, warnings, row_id, values, row_warnings)
        except (TypeError, ValueError) as exc:
            raise AnalyticalWriteError(f"Некорректная target row: {exc}") from exc
        return dict(sorted(prepared.items())), received, duplicate_count, warnings

    def _load_rows(
        self,
        *,
        table: str,
        key_column: str,
        values: dict[str, tuple[Any, ...]],
        warnings: dict[str, tuple[str, ...]],
    ) -> tuple[int, int]:
        columns = _SOURCE_COLUMNS if table == "source_rows" else _TARGET_COLUMNS
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


def _add_prepared(
    prepared: dict[str, tuple[Any, ...]],
    warnings: dict[str, tuple[str, ...]],
    key: str,
    values: tuple[Any, ...],
    row_warnings: tuple[str, ...],
) -> int:
    previous = prepared.get(key)
    if previous is not None:
        if previous[1] != values[1]:
            raise AnalyticalWriteError(f"Повторный identifier {key!r} содержит другой payload")
        return 1
    prepared[key] = values
    warnings[key] = tuple(row_warnings)
    return 0


def _decimal_columns() -> tuple[str, ...]:
    return (
        "contract_quantity",
        "period_quantity",
        "cumulative_quantity",
        "remaining_quantity",
        "unit_price",
        "contract_cost",
        "period_cost",
        "cumulative_cost",
        "total_cost",
    )


def _numeric_value(value: Any) -> Any:
    return None if value is None else value.value


def _warnings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, tuple) or any(not isinstance(item, str) for item in value):
        raise AnalyticalWriteError("warnings должен быть tuple строк")
    return value


def _decode_canonical_json(canonical_json: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(canonical_json.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AnalyticalWriteError("canonical_json rule set должен содержать UTF-8 JSON") from exc
    if not isinstance(parsed, dict):
        raise AnalyticalWriteError("canonical_json rule set должен быть JSON object")
    return parsed


def _rule_clause_values(
    content_hash: str, canonical: Mapping[str, Any], rule_set_payload_json: str
) -> list[tuple[Any, ...]]:
    values = []
    rules = canonical.get("rules")
    if not isinstance(rules, list):
        raise AnalyticalWriteError("canonical_json rule set не содержит rules")
    for rule in sorted(rules, key=lambda item: item["rule_id"]):
        if not isinstance(rule, dict) or not isinstance(rule.get("clauses"), list):
            raise AnalyticalWriteError("canonical_json содержит некорректное правило")
        scope = rule.get("scope")
        if not isinstance(scope, dict):
            raise AnalyticalWriteError("canonical_json содержит некорректный scope")
        for index, clause in enumerate(rule["clauses"]):
            if not isinstance(clause, dict):
                raise AnalyticalWriteError("canonical_json содержит некорректную clause")
            values.append(
                (
                    content_hash,
                    _required_str(rule, "rule_id"),
                    index,
                    _required_str(rule, "rule_version"),
                    _required_int(rule, "priority"),
                    "approved",
                    "baseline",
                    deterministic_json(scope),
                    _required_str(clause, "action"),
                    _required_str(clause, "match_kind"),
                    _required_str(clause, "field"),
                    _required_str(clause, "literal"),
                    _required_int(clause, "priority"),
                    _required_bool(clause, "hard_exclude"),
                    deterministic_json(_required_list(clause, "required_substrings")),
                    deterministic_json(_required_list(clause, "forbidden_substrings")),
                    deterministic_json(_required_list(clause, "source_units")),
                    deterministic_json(_required_list(clause, "excluded_units")),
                    _required_bool(clause, "include_quantity"),
                    _required_bool(clause, "include_cost"),
                    rule_set_payload_json,
                )
            )
    return values


def _required_str(payload: Mapping[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str):
        raise AnalyticalWriteError(f"canonical_json.{name} должен быть строкой")
    return value


def _required_int(payload: Mapping[str, Any], name: str) -> int:
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise AnalyticalWriteError(f"canonical_json.{name} должен быть целым")
    return value


def _required_bool(payload: Mapping[str, Any], name: str) -> bool:
    value = payload.get(name)
    if not isinstance(value, bool):
        raise AnalyticalWriteError(f"canonical_json.{name} должен быть bool")
    return value


def _required_list(payload: Mapping[str, Any], name: str) -> list[Any]:
    value = payload.get(name)
    if not isinstance(value, list):
        raise AnalyticalWriteError(f"canonical_json.{name} должен быть массивом")
    return value


def _write_diagnostics_temp(
    output: Path, records: Iterable[Mapping[str, Any]]
) -> tuple[Path, int, int]:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            count = 0
            for record in records:
                stream.write(
                    json.dumps(
                        dict(record),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                        allow_nan=False,
                    )
                )
                stream.write("\n")
                count += 1
            stream.flush()
            os.fsync(stream.fileno())
        return temporary, count, temporary.stat().st_size
    except (OSError, TypeError, ValueError) as exc:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise AnalyticalExportError(f"Не удалось подготовить diagnostics JSONL: {exc}") from exc
