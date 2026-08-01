"""Formula-bearing summary sheet for published drawing-card workbooks."""

from __future__ import annotations

from collections import defaultdict

from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import quote_sheetname

from ..models import CATEGORY_DISPLAY_NAMES, CATEGORY_ORDER, DrawingCardResultRow, ObjectBlockLayout
from ..sources.normalization import normalize_text
from .contract import COST_FORMAT, FRACTIONAL_QUANTITY_FORMAT, SUMMARY_HEADERS, SUMMARY_SHEET_NAME


def summary_row_count(layouts: list[ObjectBlockLayout]) -> int:
    """Return the number of data rows in a summary, excluding its header."""

    return len(CATEGORY_ORDER) * (len(layouts) + 1)


def _units_by_layout(
    rows: list[DrawingCardResultRow],
) -> dict[tuple[str, object], tuple[str | None, ...]]:
    units: dict[tuple[str, object], list[str | None]] = defaultdict(list)
    for row in rows:
        unit = row.result_unit.strip() if isinstance(row.result_unit, str) else None
        units[(row.object_index, row.category)].append(unit or None)
    return {key: tuple(value) for key, value in units.items()}


def _single_nonempty_unit(units: tuple[str | None, ...]) -> str | None:
    """Return a display unit only when every source row agrees on one unit."""

    if not units or any(unit is None for unit in units):
        return None
    normalized = {normalize_text(unit) for unit in units if unit is not None}
    return units[0] if len(normalized) == 1 else None


def _source_formula(
    layout: ObjectBlockLayout,
    category_column: int,
    metric_column: int,
    summary_row: int,
) -> str:
    last_row = layout.drawing_code_blocks[-1].end_row
    source_sheet = quote_sheetname(layout.sheet_name)
    category_letter = get_column_letter(category_column)
    metric_letter = get_column_letter(metric_column)
    return (
        f"=SUMIF({source_sheet}!${category_letter}${layout.data_start_row}:"
        f"${category_letter}${last_row},$B${summary_row},{source_sheet}!"
        f"${metric_letter}${layout.data_start_row}:${metric_letter}${last_row})"
    )


def _all_indices_formula(
    metric_column: int,
    first_row: int,
    last_index_row: int,
    summary_row: int,
) -> str:
    metric_letter = get_column_letter(metric_column)
    return (
        f"=SUMIF($B${first_row}:$B${last_index_row},$B${summary_row},"
        f"${metric_letter}${first_row}:${metric_letter}${last_index_row})"
    )


def add_summary_sheet(
    workbook,
    layouts: list[ObjectBlockLayout],
    rows: list[DrawingCardResultRow],
) -> None:
    """Create the stable formula summary after all card data has been written."""

    if SUMMARY_SHEET_NAME in workbook.sheetnames:
        raise ValueError(f"Summary sheet already exists: {SUMMARY_SHEET_NAME}")
    sheet = workbook.create_sheet(SUMMARY_SHEET_NAME)
    units = _units_by_layout(rows)
    header_fill = PatternFill("solid", fgColor="D9EAF7")
    for column, header in enumerate(SUMMARY_HEADERS, start=1):
        cell = sheet.cell(1, column, header)
        cell.font = Font(name="Arial", bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    row_number = 2
    for layout in layouts:
        for category in CATEGORY_ORDER:
            sheet.cell(row_number, 1, layout.object_index)
            sheet.cell(row_number, 2, CATEGORY_DISPLAY_NAMES[category])
            category_unit = _single_nonempty_unit(units.get((layout.object_index, category), ()))
            if category_unit is not None:
                sheet.cell(row_number, 3, category_unit)
                sheet.cell(
                    row_number,
                    4,
                    _source_formula(
                        layout,
                        layout.start_column + 1,
                        layout.start_column + 3,
                        row_number,
                    ),
                )
            sheet.cell(
                row_number,
                5,
                _source_formula(
                    layout,
                    layout.start_column + 1,
                    layout.start_column + 4,
                    row_number,
                ),
            )
            row_number += 1

    first_summary_row = 2
    last_index_row = row_number - 1
    for category in CATEGORY_ORDER:
        sheet.cell(row_number, 1, "Все индексы")
        sheet.cell(row_number, 2, CATEGORY_DISPLAY_NAMES[category])
        category_units = tuple(
            sheet.cell(index_row, 3).value
            for index_row in range(first_summary_row, last_index_row + 1)
            if sheet.cell(index_row, 2).value == CATEGORY_DISPLAY_NAMES[category]
        )
        category_unit = _single_nonempty_unit(category_units)
        if category_unit is not None:
            sheet.cell(row_number, 3, category_unit)
            sheet.cell(
                row_number,
                4,
                _all_indices_formula(4, first_summary_row, last_index_row, row_number),
            )
        sheet.cell(
            row_number,
            5,
            _all_indices_formula(5, first_summary_row, last_index_row, row_number),
        )
        row_number += 1

    for row in range(2, row_number):
        sheet.cell(row, 4).number_format = FRACTIONAL_QUANTITY_FORMAT
        sheet.cell(row, 5).number_format = COST_FORMAT
        for column in range(1, 6):
            sheet.cell(row, column).font = Font(name="Arial")
            sheet.cell(row, column).alignment = Alignment(vertical="top", wrap_text=True)
    for column, width in enumerate((18, 48, 12, 14, 18), start=1):
        sheet.column_dimensions[get_column_letter(column)].width = width
    sheet.freeze_panes = "A2"
