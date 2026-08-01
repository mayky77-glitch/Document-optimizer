"""Formula-bearing card-style summary sheet for published drawing-card workbooks."""

from __future__ import annotations

from collections import defaultdict

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import quote_sheetname

from ..models import CATEGORY_DISPLAY_NAMES, CATEGORY_ORDER, DrawingCardResultRow, ObjectBlockLayout
from ..sources.normalization import normalize_text
from .contract import (
    COST_FORMAT,
    FRACTIONAL_QUANTITY_FORMAT,
    SUMMARY_BLOCK_COLUMN_SPAN,
    SUMMARY_BLOCK_ROW_SPAN,
    SUMMARY_BLOCKS_PER_ROW,
    SUMMARY_HEADERS,
    SUMMARY_SHEET_NAME,
)

_TITLE_FILL = PatternFill("solid", fgColor="C6E0B4")
_HEADER_FILL = PatternFill("solid", fgColor="E2F0D9")
_BORDER = Border(
    left=Side(style="thin", color="7F8C7A"),
    right=Side(style="thin", color="7F8C7A"),
    top=Side(style="thin", color="7F8C7A"),
    bottom=Side(style="thin", color="7F8C7A"),
)


def summary_block_position(block_number: int) -> tuple[int, int]:
    """Return the top-left cell for a compact summary card block."""

    return (
        1 + (block_number // SUMMARY_BLOCKS_PER_ROW) * SUMMARY_BLOCK_ROW_SPAN,
        1 + (block_number % SUMMARY_BLOCKS_PER_ROW) * SUMMARY_BLOCK_COLUMN_SPAN,
    )


def summary_row_count(layouts: list[ObjectBlockLayout]) -> int:
    """Return the summary sheet height used by all index cards and the grand total."""

    total_block_number = len(layouts)
    total_start_row, _ = summary_block_position(total_block_number)
    return total_start_row + len(CATEGORY_ORDER) + 1


def _units_by_layout(
    rows: list[DrawingCardResultRow],
) -> dict[tuple[str, object], tuple[str | None, ...]]:
    units: dict[tuple[str, object], list[str | None]] = defaultdict(list)
    for row in rows:
        unit = row.result_unit.strip() if isinstance(row.result_unit, str) else None
        units[(row.object_index, row.category)].append(unit or None)
    return {key: tuple(value) for key, value in units.items()}


def _single_nonempty_unit(units: tuple[str | None, ...]) -> str | None:
    if not units or any(unit is None for unit in units):
        return None
    normalized = {normalize_text(unit) for unit in units if unit is not None}
    return units[0] if len(normalized) == 1 else None


def _source_formula(
    layout: ObjectBlockLayout,
    category_column: int,
    metric_column: int,
    summary_row: int,
    summary_category_column: int = 1,
) -> str:
    last_row = layout.drawing_code_blocks[-1].end_row
    source_sheet = quote_sheetname(layout.sheet_name)
    category_letter = get_column_letter(category_column)
    metric_letter = get_column_letter(metric_column)
    summary_category_letter = get_column_letter(summary_category_column)
    return (
        f"=SUMIF({source_sheet}!${category_letter}${layout.data_start_row}:"
        f"${category_letter}${last_row},${summary_category_letter}${summary_row},{source_sheet}!"
        f"${metric_letter}${layout.data_start_row}:${metric_letter}${last_row})"
    )


def _all_indices_formula(metric_cells: list[str]) -> str:
    return f"=SUM({','.join(metric_cells)})"


def _style_block(sheet, *, start_row: int, start_column: int, title: str) -> None:
    end_column = start_column + len(SUMMARY_HEADERS) - 1
    sheet.merge_cells(
        start_row=start_row,
        start_column=start_column,
        end_row=start_row,
        end_column=end_column,
    )
    title_cell = sheet.cell(start_row, start_column, title)
    title_cell.font = Font(name="Arial", bold=True, size=12)
    title_cell.fill = _TITLE_FILL
    title_cell.alignment = Alignment(horizontal="left", vertical="center")
    title_cell.border = _BORDER
    for column, header in enumerate(SUMMARY_HEADERS, start=start_column):
        cell = sheet.cell(start_row + 1, column, header)
        cell.font = Font(name="Arial", bold=True)
        cell.fill = _HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = _BORDER
    for row in range(start_row + 2, start_row + 2 + len(CATEGORY_ORDER)):
        for column in range(start_column, end_column + 1):
            cell = sheet.cell(row, column)
            cell.font = Font(name="Arial")
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = _BORDER


def add_summary_sheet(
    workbook,
    layouts: list[ObjectBlockLayout],
    rows: list[DrawingCardResultRow],
) -> None:
    """Create horizontal index cards and a separate formula-bearing grand-total card."""

    if SUMMARY_SHEET_NAME in workbook.sheetnames:
        raise ValueError(f"Summary sheet already exists: {SUMMARY_SHEET_NAME}")
    sheet = workbook.create_sheet(SUMMARY_SHEET_NAME)
    units = _units_by_layout(rows)
    index_metric_cells: dict[object, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))

    for block_number, layout in enumerate(layouts):
        start_row, start_column = summary_block_position(block_number)
        _style_block(
            sheet,
            start_row=start_row,
            start_column=start_column,
            title=f"Индекс объекта: {layout.object_index}",
        )
        for offset, category in enumerate(CATEGORY_ORDER):
            row = start_row + 2 + offset
            category_cell = sheet.cell(row, start_column, CATEGORY_DISPLAY_NAMES[category])
            unit = _single_nonempty_unit(units.get((layout.object_index, category), ()))
            if unit is not None:
                sheet.cell(row, start_column + 1, unit)
                quantity = sheet.cell(
                    row,
                    start_column + 2,
                    _source_formula(
                        layout,
                        layout.start_column + 1,
                        layout.start_column + 3,
                        row,
                        start_column,
                    ),
                )
                quantity.number_format = FRACTIONAL_QUANTITY_FORMAT
                index_metric_cells[category][2].append(quantity.coordinate)
            cost = sheet.cell(
                row,
                start_column + 3,
                _source_formula(
                    layout,
                    layout.start_column + 1,
                    layout.start_column + 4,
                    row,
                    start_column,
                ),
            )
            cost.number_format = COST_FORMAT
            index_metric_cells[category][3].append(cost.coordinate)
            category_cell.alignment = Alignment(vertical="top", wrap_text=True)

    total_start_row, total_start_column = summary_block_position(len(layouts))
    _style_block(
        sheet,
        start_row=total_start_row,
        start_column=total_start_column,
        title="Все индексы",
    )
    for offset, category in enumerate(CATEGORY_ORDER):
        row = total_start_row + 2 + offset
        sheet.cell(row, total_start_column, CATEGORY_DISPLAY_NAMES[category])
        category_units = tuple(
            _single_nonempty_unit(units.get((layout.object_index, category), ()))
            for layout in layouts
        )
        unit = _single_nonempty_unit(category_units)
        if unit is not None:
            sheet.cell(row, total_start_column + 1, unit)
            quantity = sheet.cell(
                row,
                total_start_column + 2,
                _all_indices_formula(index_metric_cells[category][2]),
            )
            quantity.number_format = FRACTIONAL_QUANTITY_FORMAT
        cost = sheet.cell(
            row,
            total_start_column + 3,
            _all_indices_formula(index_metric_cells[category][3]),
        )
        cost.number_format = COST_FORMAT

    for column in range(1, sheet.max_column + 1):
        offset = (column - 1) % SUMMARY_BLOCK_COLUMN_SPAN
        sheet.column_dimensions[get_column_letter(column)].width = (38, 12, 15, 20, 3, 3)[offset]
    for row in range(1, sheet.max_row + 1):
        sheet.row_dimensions[row].height = 22 if row % SUMMARY_BLOCK_ROW_SPAN < 2 else 30
    sheet.freeze_panes = "A3"
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.print_options.horizontalCentered = True
    sheet.print_area = f"A1:{get_column_letter(sheet.max_column)}{sheet.max_row}"
