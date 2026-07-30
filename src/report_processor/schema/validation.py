"""Validation issues supplement statuses; expected uncertainty is not an exception."""

from __future__ import annotations

from collections import Counter

from report_processor.schema.models import (
    SchemaValidationIssue,
    SheetColumnRequirements,
    SheetType,
    WorksheetSchema,
)


def validate_worksheet_schema(
    schema: WorksheetSchema,
    requirements: SheetColumnRequirements | None,
) -> tuple[SchemaValidationIssue, ...]:
    issues: list[SchemaValidationIssue] = []
    if schema.header_start_row is None or schema.header_end_row is None:
        issues.append(SchemaValidationIssue("HEADER_NOT_FOUND", "error", "Заголовок не найден"))
    elif schema.header_start_row > schema.header_end_row:
        issues.append(
            SchemaValidationIssue(
                "INVALID_HEADER_RANGE",
                "error",
                "Начальная строка заголовка находится после конечной",
                related_rows=(schema.header_start_row, schema.header_end_row),
            )
        )
    if (
        schema.data_start_row is not None
        and schema.header_end_row is not None
        and schema.data_start_row <= schema.header_end_row
    ):
        issues.append(
            SchemaValidationIssue(
                "INVALID_DATA_START",
                "error",
                "Область данных должна начинаться после заголовка",
                related_rows=(schema.data_start_row, schema.header_end_row),
            )
        )

    resolved = [item for item in schema.columns if item.status == "OK"]
    duplicate_physical = [
        column
        for column, count in Counter(item.column_letter for item in resolved).items()
        if column is not None and count > 1
    ]
    if duplicate_physical:
        issues.append(
            SchemaValidationIssue(
                "DUPLICATE_PHYSICAL_COLUMN",
                "error",
                "Один Excel-столбец назначен нескольким логическим полям",
                related_columns=tuple(duplicate_physical),
            )
        )

    if schema.sheet_type in {SheetType.TITLE, SheetType.TECHNICAL} and len(resolved) >= 3:
        issues.append(
            SchemaValidationIssue(
                "SHEET_TYPE_COLUMN_CONFLICT",
                "warning",
                "Тип листа конфликтует с набором найденных табличных столбцов",
                related_columns=tuple(item.logical_column.value for item in resolved),
            )
        )

    if requirements:
        found = {item.logical_column for item in resolved}
        missing = tuple(item.value for item in requirements.required if item not in found)
        if missing:
            issues.append(
                SchemaValidationIssue(
                    "MISSING_REQUIRED_COLUMNS",
                    "warning",
                    "Не найдены обязательные логические столбцы",
                    related_columns=missing,
                )
            )

    if schema.first_table_column is not None and schema.last_table_column is not None:
        outside = tuple(
            item.column_letter or ""
            for item in resolved
            if item.column_index is not None
            and not schema.first_table_column <= item.column_index <= schema.last_table_column
        )
        if outside:
            issues.append(
                SchemaValidationIssue(
                    "COLUMN_OUTSIDE_TABLE_BOUNDS",
                    "warning",
                    "Разрешённые столбцы выходят за горизонтальные границы таблицы",
                    related_columns=outside,
                )
            )
    if schema.confidence < 0.70:
        issues.append(
            SchemaValidationIssue(
                "LOW_CONFIDENCE_SCHEMA",
                "warning",
                f"Уверенность схемы ниже 0.70: {schema.confidence:.3f}",
            )
        )
    return tuple(issues)
