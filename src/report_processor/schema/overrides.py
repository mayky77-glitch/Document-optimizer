"""Explicit programmatic overrides; nothing is written back to Excel."""

from __future__ import annotations

from openpyxl.utils.cell import column_index_from_string, get_column_letter

from report_processor.schema.models import (
    ColumnResolution,
    ComposedHeader,
    WorksheetSchemaOverride,
)


def validate_worksheet_override(
    override: WorksheetSchemaOverride,
    *,
    sheet_names: tuple[str, ...],
    max_column: int,
) -> tuple[str, ...]:
    errors: list[str] = []
    if override.sheet_name not in sheet_names:
        errors.append("OVERRIDE_SHEET_NOT_FOUND")
    if (
        override.header_start_row is not None
        and override.header_end_row is not None
        and override.header_start_row > override.header_end_row
    ):
        errors.append("OVERRIDE_HEADER_RANGE_INVALID")
    for item in override.column_overrides:
        try:
            index = column_index_from_string(item.column.upper())
        except ValueError:
            errors.append(f"OVERRIDE_COLUMN_INVALID:{item.column}")
            continue
        if index > max_column:
            errors.append(f"OVERRIDE_COLUMN_OUTSIDE_SCAN:{item.column.upper()}")
    return tuple(errors)


def apply_column_overrides(
    columns: tuple[ColumnResolution, ...],
    headers: tuple[ComposedHeader, ...],
    override: WorksheetSchemaOverride | None,
) -> tuple[ColumnResolution, ...]:
    if override is None or not override.column_overrides:
        return columns
    by_logical = {item.logical_column: item for item in columns}
    header_by_index = {item.column_index: item for item in headers}
    for item in override.column_overrides:
        index = column_index_from_string(item.column.upper())
        header = header_by_index.get(index)
        existing = by_logical.get(item.logical_column)
        resolution = ColumnResolution(
            logical_column=item.logical_column,
            column_index=index,
            column_letter=get_column_letter(index),
            header_text=header.raw_text if header else None,
            confidence=1.0,
            matched_rule="manual_override",
            alternatives=existing.alternatives if existing else (),
            status="OK",
            warnings=("MANUAL_OVERRIDE_APPLIED",),
            is_manual=True,
        )
        by_logical[item.logical_column] = resolution
    return tuple(sorted(by_logical.values(), key=lambda value: value.logical_column.value))
