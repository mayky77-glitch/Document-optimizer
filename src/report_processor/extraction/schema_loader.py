"""Read block-5 schema JSON without changing its public serialization format."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from report_processor.schema import (
    ColumnResolution,
    LogicalColumn,
    SheetType,
    WorkbookSchema,
    WorksheetSchema,
)

from .exceptions import ExtractionSchemaError


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ExtractionSchemaError(code)
    return value


def _string(value: object, code: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise ExtractionSchemaError(code)
    return value


def _string_list(value: object, code: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ExtractionSchemaError(code)
    return tuple(value)


def _positive_index(value: object, code: str, *, nullable: bool = True) -> int | None:
    if value is None and nullable:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ExtractionSchemaError(code)
    return value


def _confidence(value: object, code: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ExtractionSchemaError(code)
    try:
        result = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ExtractionSchemaError(code) from exc
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ExtractionSchemaError(code)
    return result


def _logical_column(value: object) -> LogicalColumn:
    try:
        return LogicalColumn(_string(value, "LOGICAL_COLUMN_INVALID"))
    except ValueError as exc:
        raise ExtractionSchemaError(f"UNKNOWN_LOGICAL_COLUMN:{value}") from exc


def _sheet_type(value: object) -> SheetType:
    try:
        return SheetType(_string(value, "SHEET_TYPE_INVALID"))
    except ValueError as exc:
        raise ExtractionSchemaError(f"UNKNOWN_SHEET_TYPE:{value}") from exc


def _column(payload: Mapping[str, Any]) -> ColumnResolution | None:
    status = _string(payload.get("status", "COLUMN_NOT_FOUND"), "COLUMN_STATUS_INVALID")
    index = payload.get("column_index", payload.get("physical_column"))
    logical_column = _logical_column(payload.get("logical_column"))
    column_letter = _string(payload.get("column_letter"), "COLUMN_LETTER_INVALID", nullable=True)
    header_text = _string(payload.get("header_text"), "COLUMN_HEADER_INVALID", nullable=True)
    confidence = _confidence(payload.get("confidence", 0.0), "COLUMN_CONFIDENCE_INVALID")
    matched_rule = _string(payload.get("matched_rule"), "MATCHED_RULE_INVALID", nullable=True)
    warnings = _string_list(payload.get("warnings", []), "COLUMN_WARNINGS_INVALID")
    is_manual = _bool(payload.get("is_manual", False), "COLUMN_IS_MANUAL_INVALID")
    if index is None and status != "OK":
        return None
    column_index = _positive_index(index, "COLUMN_INDEX_INVALID", nullable=False)
    return ColumnResolution(
        logical_column=logical_column,
        column_index=column_index,
        column_letter=column_letter,
        header_text=header_text,
        confidence=confidence,
        matched_rule=matched_rule,
        alternatives=(),
        status=status,
        warnings=warnings,
        is_manual=is_manual,
    )


def _bool(value: object, code: str) -> bool:
    if not isinstance(value, bool):
        raise ExtractionSchemaError(code)
    return value


def _worksheet(payload: Mapping[str, Any]) -> WorksheetSchema:
    columns = payload.get("columns")
    if not isinstance(columns, list):
        raise ExtractionSchemaError("WORKSHEET_COLUMNS_INVALID")
    header_start_row = _positive_index(payload.get("header_start_row"), "HEADER_START_ROW_INVALID")
    header_end_row = _positive_index(payload.get("header_end_row"), "HEADER_END_ROW_INVALID")
    data_start_raw = payload.get("data_start_row")
    data_start_row = (
        _positive_index(data_start_raw, "DATA_START_ROW_INVALID")
        if data_start_raw is not None
        else (header_end_row + 1 if header_end_row is not None else None)
    )
    resolved_columns = []
    for item in columns:
        column = _column(_mapping(item, "COLUMN_PAYLOAD_INVALID"))
        if column is not None:
            resolved_columns.append(column)
    return WorksheetSchema(
        sheet_name=_string(payload.get("sheet_name"), "SHEET_NAME_INVALID") or "",
        sheet_type=_sheet_type(payload.get("sheet_type")),
        classification=None,
        header_start_row=header_start_row,
        header_end_row=header_end_row,
        data_start_row=data_start_row,
        first_table_column=_positive_index(
            payload.get("first_table_column"), "FIRST_TABLE_COLUMN_INVALID"
        ),
        last_table_column=_positive_index(
            payload.get("last_table_column"), "LAST_TABLE_COLUMN_INVALID"
        ),
        headers=(),
        columns=tuple(resolved_columns),
        confidence=_confidence(payload.get("confidence", 0.0), "WORKSHEET_CONFIDENCE_INVALID"),
        status=_string(payload.get("status", "SCHEMA_DETECTION_FAILED"), "WORKSHEET_STATUS_INVALID")
        or "",
        warnings=_string_list(payload.get("warnings", []), "WORKSHEET_WARNINGS_INVALID"),
        validation_issues=(),
        manual_overrides=_string_list(
            payload.get("manual_overrides", []), "MANUAL_OVERRIDES_INVALID"
        ),
    )


def _sheet_mapping(
    value: object,
    *,
    code: str,
    nullable_values: bool,
) -> dict[str, tuple[str, ...] | str | None]:
    payload = _mapping(value, code)
    result: dict[str, tuple[str, ...] | str | None] = {}
    for key, item in payload.items():
        if not isinstance(key, str):
            raise ExtractionSchemaError(code)
        if nullable_values:
            result[key] = _string(item, code, nullable=True)
        else:
            result[key] = _string_list(item, code)
    return result


def load_workbook_schema_json(path: Path) -> WorkbookSchema:
    """Load only schema fields required by extraction from block-5 JSON output."""

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExtractionSchemaError(f"SCHEMA_READ_FAILED:{exc}") from exc
    payload = _mapping(payload, "WORKBOOK_PAYLOAD_INVALID")
    worksheets = payload.get("worksheets", payload.get("sheets"))
    if not isinstance(worksheets, list):
        raise ExtractionSchemaError("WORKBOOK_WORKSHEETS_INVALID")
    sheets_by_type = _sheet_mapping(
        payload.get("sheets_by_type", {}),
        code="SHEETS_BY_TYPE_INVALID",
        nullable_values=False,
    )
    primary_sheets = _sheet_mapping(
        payload.get("primary_sheets", {}),
        code="PRIMARY_SHEETS_INVALID",
        nullable_values=True,
    )
    return WorkbookSchema(
        source_file_id=_string(
            payload.get("source_file_id", payload.get("file_id", "")),
            "SOURCE_FILE_ID_INVALID",
        )
        or "",
        filename=_string(
            payload.get("filename", payload.get("source_filename", "")), "FILENAME_INVALID"
        )
        or "",
        worksheets=tuple(
            _worksheet(_mapping(item, "WORKSHEET_PAYLOAD_INVALID")) for item in worksheets
        ),
        sheets_by_type={
            key: value for key, value in sheets_by_type.items() if isinstance(value, tuple)
        },
        primary_sheets=primary_sheets,
        confidence=_confidence(payload.get("confidence", 0.0), "WORKBOOK_CONFIDENCE_INVALID"),
        status=_string(payload.get("status", "SCHEMA_DETECTION_FAILED"), "WORKBOOK_STATUS_INVALID")
        or "",
        warnings=_string_list(payload.get("warnings", []), "WORKBOOK_WARNINGS_INVALID"),
    )
