"""Формирование семантически типизированных Polars DataFrame."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .models import CachedWorksheet
from .normalization import (
    infer_column_role,
    is_boolean_header,
    is_text_identifier_header,
    make_unique_headers,
    parse_boolean_value,
    stringify_cell,
    stringify_identifier_cell,
    to_float,
)


def build_typed_dataframe(
    polars: Any,
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
) -> tuple[Any, dict[str, str]]:
    """Создаёт DataFrame в памяти с семантическими типами колонок."""
    column_types: dict[str, str] = {}
    series: list[Any] = []

    for column_index, header in enumerate(headers):
        values = [
            row[column_index] if column_index < len(row) else None
            for row in rows
        ]
        role = infer_column_role(header, values)
        column_types[header] = role

        if role == "float":
            converted = [to_float(value) for value in values]
            series.append(polars.Series(header, converted, dtype=polars.Float64))
        elif role == "boolean":
            allow_numeric = is_boolean_header(header)
            converted = [
                parse_boolean_value(value, allow_numeric=allow_numeric)[1]
                for value in values
            ]
            series.append(polars.Series(header, converted, dtype=polars.Boolean))
        elif role == "datetime":
            series.append(polars.Series(header, values, dtype=polars.Datetime))
        elif role == "date":
            series.append(polars.Series(header, values, dtype=polars.Date))
        else:
            stringify = (
                stringify_identifier_cell
                if is_text_identifier_header(header)
                else stringify_cell
            )
            converted = [stringify(value) for value in values]
            series.append(polars.Series(header, converted, dtype=polars.String))

    dataframe = polars.DataFrame(series)
    return dataframe, column_types

def build_full_cached_sheet_dataframe(
    polars: Any,
    worksheet: CachedWorksheet,
) -> tuple[Any, dict[str, Any]]:
    """Сохраняет весь лист в памяти без повторного открытия XLSX."""
    if worksheet.max_row <= 0 or worksheet.max_column <= 0:
        return polars.DataFrame(), {
            "mode": "full_cached_sheet",
            "written_rows": 0,
            "columns": 0,
            "column_types": {},
        }

    first_row = [
        worksheet.cell(row=1, column=column).value
        for column in range(1, worksheet.max_column + 1)
    ]
    headers = make_unique_headers(first_row, worksheet.max_column)
    rows = [
        [
            worksheet.cell(row=row_number, column=column).value
            for column in range(1, worksheet.max_column + 1)
        ]
        for row_number in range(2, worksheet.max_row + 1)
    ]
    dataframe, column_types = build_typed_dataframe(polars, headers, rows)

    return dataframe, {
        "mode": "full_cached_sheet",
        "written_rows": dataframe.height,
        "columns": dataframe.width,
        "output_columns": headers,
        "column_types": column_types,
        "numeric_rounding": None,
    }
