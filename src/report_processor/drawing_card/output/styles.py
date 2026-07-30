"""Template-derived style cloning helpers."""

from __future__ import annotations

from copy import copy

from openpyxl.worksheet.worksheet import Worksheet


def copy_cell_style(source, target) -> None:
    if source.has_style:
        target._style = copy(source._style)
    if source.number_format:
        target.number_format = source.number_format
    target.font = copy(source.font)
    target.fill = copy(source.fill)
    target.border = copy(source.border)
    target.alignment = copy(source.alignment)
    target.protection = copy(source.protection)


def clone_row_style(
    worksheet: Worksheet,
    *,
    source_row: int,
    target_row: int,
    start_column: int,
    end_column: int,
) -> None:
    source_dimension = worksheet.row_dimensions[source_row]
    target_dimension = worksheet.row_dimensions[target_row]
    target_dimension.height = source_dimension.height
    target_dimension.hidden = source_dimension.hidden
    for column in range(start_column, end_column + 1):
        copy_cell_style(worksheet.cell(source_row, column), worksheet.cell(target_row, column))


def clone_block_columns(
    worksheet: Worksheet,
    *,
    source_start: int,
    target_start: int,
    width: int = 5,
) -> None:
    from openpyxl.utils import get_column_letter

    for offset in range(width):
        source_letter = get_column_letter(source_start + offset)
        target_letter = get_column_letter(target_start + offset)
        source_dimension = worksheet.column_dimensions[source_letter]
        target_dimension = worksheet.column_dimensions[target_letter]
        target_dimension.width = source_dimension.width
        target_dimension.hidden = source_dimension.hidden
        for row in range(2, max(12, worksheet.max_row) + 1):
            copy_cell_style(
                worksheet.cell(row, source_start + offset),
                worksheet.cell(row, target_start + offset),
            )
