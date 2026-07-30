from __future__ import annotations

import re
from collections.abc import Iterable

from openpyxl.utils.cell import column_index_from_string

from report_processor.domain.exceptions import CellReadError
from report_processor.domain.statuses import StatusCode

from .models import CellReference, CellSnapshot, DualWorkbookSession
from .workbook_session import validate_dual_workbook_session

_CELL_RE = re.compile(r"^([A-Za-z]{1,3})([1-9][0-9]{0,6})$")
_MAX_ROW = 1_048_576
_MAX_COLUMN = 16_384


def normalize_cell_coordinate(coordinate: str) -> str:
    match = _CELL_RE.fullmatch(coordinate.strip())
    if match is None:
        raise CellReadError(
            StatusCode.INVALID_CELL_COORDINATE,
            f"Некорректная координата ячейки: {coordinate}",
        )
    column_letters, row_text = match.groups()
    column_index = column_index_from_string(column_letters.upper())
    row_index = int(row_text)
    if column_index > _MAX_COLUMN or row_index > _MAX_ROW:
        raise CellReadError(
            StatusCode.INVALID_CELL_COORDINATE,
            f"Координата выходит за пределы Excel: {coordinate}",
        )
    return f"{column_letters.upper()}{row_index}"


def _excel_error(value: object, data_type: str | None) -> str | None:
    return str(value) if data_type == "e" and value is not None else None


def read_cell_snapshot(
    session: DualWorkbookSession,
    sheet_name: str,
    coordinate: str,
) -> CellSnapshot:
    validate_dual_workbook_session(session)
    normalized = normalize_cell_coordinate(coordinate)
    if sheet_name not in session.formula_workbook.sheetnames:
        raise CellReadError(
            StatusCode.SHEET_NOT_FOUND,
            f"Лист не найден: {sheet_name}",
        )

    try:
        formula_cell = session.formula_workbook[sheet_name][normalized]
        cached_cell = session.value_workbook[sheet_name][normalized]
    except (KeyError, ValueError, IndexError) as error:
        raise CellReadError(
            StatusCode.CELL_READ_FAILED,
            f"Не удалось прочитать ячейку {sheet_name}!{normalized}: {error}",
        ) from error

    formula_value = formula_cell.value
    cached_value = cached_cell.value
    formula_data_type = getattr(formula_cell, "data_type", None)
    cached_data_type = getattr(cached_cell, "data_type", None)
    is_formula = formula_data_type == "f" or (
        isinstance(formula_value, str) and formula_value.startswith("=")
    )
    formula_error = _excel_error(formula_value, formula_data_type)
    cached_error = _excel_error(cached_value, cached_data_type)
    warnings: list[str] = []

    if cached_data_type == "f" or (formula_data_type == "f" and not is_formula):
        status = StatusCode.FORMULA_VIEW_MISMATCH
        warnings.append(StatusCode.FORMULA_VIEW_MISMATCH.value)
    elif formula_error is not None or cached_error is not None:
        status = StatusCode.REAL_EXCEL_ERROR
    elif is_formula and cached_value is not None:
        status = StatusCode.FORMULA_WITH_CACHED_VALUE
    elif is_formula:
        status = StatusCode.FORMULA_WITHOUT_CACHED_VALUE
    else:
        status = StatusCode.OK

    return CellSnapshot(
        sheet_name=sheet_name,
        coordinate=normalized,
        formula_value=formula_value,
        cached_value=cached_value,
        formula_data_type=formula_data_type,
        cached_data_type=cached_data_type,
        is_formula=is_formula,
        has_cached_value=cached_value is not None,
        formula_error=formula_error,
        cached_error=cached_error,
        status=status.value,
        warnings=tuple(warnings),
    )


def read_cell_snapshots(
    session: DualWorkbookSession,
    requests: Iterable[CellReference],
    *,
    max_cells: int = 1_000,
) -> tuple[CellSnapshot, ...]:
    result: list[CellSnapshot] = []
    for index, reference in enumerate(requests, start=1):
        if index > max_cells:
            raise ValueError(f"За один запрос разрешено не более {max_cells} ячеек")
        result.append(read_cell_snapshot(session, reference.sheet_name, reference.coordinate))
    return tuple(result)
