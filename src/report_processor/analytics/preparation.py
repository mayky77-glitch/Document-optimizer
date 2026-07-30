"""Deterministic conversion of frozen upstream contracts into analytical rows."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict
from hashlib import sha256
from typing import Any

from report_processor.business_rules.models import ValidatedRuleSet
from report_processor.normalization.models import NormalizedSourceRow
from report_processor.target_report.models import TargetReportRow

from .exceptions import AnalyticalWriteError
from .serialization import deterministic_json, payload_hash, strict_decimal, target_row_id

SOURCE_COLUMNS = (
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
TARGET_COLUMNS = (
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
RULE_SET_COLUMNS = (
    "content_hash",
    "configuration_version",
    "rule_set_version",
    "defaults_json",
    "canonical_json",
    "payload_hash",
)
RULE_CLAUSE_COLUMNS = (
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
PreparedRows = tuple[dict[str, tuple[Any, ...]], int, int, dict[str, tuple[str, ...]]]


def prepare_source_rows(rows: Iterable[NormalizedSourceRow]) -> PreparedRows:
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
                    for name, value in zip(_DECIMAL_COLUMNS, row.decimals, strict=True)
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


def prepare_target_rows(
    rows: Iterable[TargetReportRow], source_id: str, fingerprint: str
) -> PreparedRows:
    prepared: dict[str, tuple[Any, ...]] = {}
    warnings: dict[str, tuple[str, ...]] = {}
    received = duplicate_count = 0
    try:
        for row in rows:
            received += 1
            if not isinstance(row, TargetReportRow) or not row.sheet_name or row.row_number < 1:
                raise TypeError("ожидался TargetReportRow с sheet_name и положительным row_number")
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


def prepare_rule_set(
    rule_set: ValidatedRuleSet,
) -> tuple[tuple[Any, ...], list[tuple[Any, ...]]]:
    if not isinstance(rule_set, ValidatedRuleSet):
        raise AnalyticalWriteError("ожидался ValidatedRuleSet")
    if rule_set.content_hash != sha256(rule_set.canonical_json).hexdigest():
        raise AnalyticalWriteError("content_hash не соответствует canonical_json")
    canonical = _decode_canonical_json(rule_set.canonical_json)
    payload_json, payload_digest = payload_hash(canonical)
    values = (
        rule_set.content_hash,
        rule_set.configuration_version.value,
        rule_set.rule_set_version,
        deterministic_json(asdict(rule_set.defaults)),
        rule_set.canonical_json.decode("utf-8"),
        payload_digest,
    )
    return values, _rule_clause_values(rule_set.content_hash, canonical, payload_json)


_DECIMAL_COLUMNS = (
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
    warnings[key] = row_warnings
    return 0


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
