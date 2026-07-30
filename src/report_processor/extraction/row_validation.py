from __future__ import annotations

import math
from decimal import Decimal

from openpyxl.utils.cell import column_index_from_string, coordinate_from_string

from .models import CanonicalSourceRow, ExtractedCellValue, RowValidationIssue
from .statuses import (
    CellValueStatus,
    EffectiveValueSource,
    IssueSeverity,
)

_NUMERIC_FIELDS = (
    "contract_quantity",
    "current_period_quantity",
    "cumulative_quantity",
    "remaining_quantity",
    "unit_price",
    "contract_cost",
    "current_period_cost",
    "cumulative_cost",
    "total_cost",
)
_ALLOWED_VALUE_SOURCES = {item.value for item in EffectiveValueSource}
_ERROR_STATUSES = {
    CellValueStatus.EXCEL_ERROR.value,
    CellValueStatus.VALUE_READ_FAILED.value,
}


def _issue(
    code: str,
    severity: IssueSeverity,
    message: str,
    *coordinates: str,
) -> RowValidationIssue:
    return RowValidationIssue(code, severity.value, message, tuple(coordinates))


def _is_non_finite(value: object) -> bool:
    if isinstance(value, Decimal):
        return not value.is_finite()
    if isinstance(value, float):
        return not math.isfinite(value)
    return False


def _validate_coordinate(
    row: CanonicalSourceRow,
    cell: ExtractedCellValue,
) -> list[RowValidationIssue]:
    issues: list[RowValidationIssue] = []
    location = cell.provenance.location
    if not cell.coordinate or location.coordinate != cell.coordinate:
        issues.append(
            _issue(
                "CELL_COORDINATE_MISMATCH",
                IssueSeverity.ERROR,
                "Координата значения не совпадает с provenance",
                cell.coordinate,
            )
        )
        return issues
    try:
        letter, row_number = coordinate_from_string(cell.coordinate)
        column_number = column_index_from_string(letter)
    except ValueError:
        issues.append(
            _issue(
                "CELL_COORDINATE_INVALID",
                IssueSeverity.ERROR,
                "Некорректная Excel-координата",
                cell.coordinate,
            )
        )
        return issues
    if (
        location.row_number != row_number
        or location.column_number != column_number
        or (location.column_letter or "").upper() != letter.upper()
    ):
        issues.append(
            _issue(
                "CELL_LOCATION_INCONSISTENT",
                IssueSeverity.ERROR,
                "Номер строки/столбца не соответствует координате",
                cell.coordinate,
            )
        )
    row_location = row.source_location
    if (
        location.source_file_id != row_location.source_file_id
        or location.filename != row_location.filename
        or location.sheet_name != row_location.sheet_name
        or location.sheet_type != row_location.sheet_type
        or location.row_number != row_location.row_number
    ):
        issues.append(
            _issue(
                "CELL_ROW_LOCATION_MISMATCH",
                IssueSeverity.ERROR,
                "Provenance ячейки относится к другой исходной строке",
                cell.coordinate,
            )
        )
    return issues


def _validate_cell_state(cell: ExtractedCellValue) -> list[RowValidationIssue]:
    issues: list[RowValidationIssue] = []
    source = cell.effective_value_source
    if source not in _ALLOWED_VALUE_SOURCES:
        issues.append(
            _issue(
                "VALUE_SOURCE_INVALID",
                IssueSeverity.ERROR,
                f"Недопустимый effective_value_source: {source}",
                cell.coordinate,
            )
        )
    if cell.is_empty != (cell.status == CellValueStatus.EMPTY.value):
        issues.append(
            _issue(
                "EMPTY_STATUS_CONTRADICTION",
                IssueSeverity.ERROR,
                "is_empty не соответствует статусу EMPTY",
                cell.coordinate,
            )
        )
    if cell.is_empty and cell.effective_value is not None:
        issues.append(
            _issue(
                "EMPTY_VALUE_CONTRADICTION",
                IssueSeverity.ERROR,
                "is_empty=True при непустом effective_value",
                cell.coordinate,
            )
        )
    if cell.is_error != (cell.status in _ERROR_STATUSES):
        issues.append(
            _issue(
                "ERROR_STATUS_CONTRADICTION",
                IssueSeverity.ERROR,
                "is_error не соответствует статусу ошибки",
                cell.coordinate,
            )
        )
    provenance = cell.provenance
    if cell.is_formula:
        if not isinstance(cell.raw_formula_value, str) or not cell.raw_formula_value.startswith(
            "="
        ):
            issues.append(
                _issue(
                    "FORMULA_RAW_VALUE_INVALID",
                    IssueSeverity.ERROR,
                    "Формульная ячейка не содержит исходную формулу",
                    cell.coordinate,
                )
            )
        if provenance.formula != cell.raw_formula_value:
            issues.append(
                _issue(
                    "FORMULA_PROVENANCE_MISMATCH",
                    IssueSeverity.ERROR,
                    "Формула не совпадает с provenance",
                    cell.coordinate,
                )
            )
    elif provenance.formula is not None:
        issues.append(
            _issue(
                "UNEXPECTED_FORMULA_PROVENANCE",
                IssueSeverity.ERROR,
                "У литеральной ячейки сохранена формула",
                cell.coordinate,
            )
        )
    cached_expected = (
        cell.is_formula
        and cell.raw_cached_value is not None
        and cell.status != CellValueStatus.EXCEL_ERROR.value
    )
    if provenance.cached_value_available != cached_expected:
        issues.append(
            _issue(
                "CACHED_VALUE_FLAG_MISMATCH",
                IssueSeverity.ERROR,
                "Флаг наличия кэшированного значения противоречив",
                cell.coordinate,
            )
        )
    for value in (
        cell.raw_formula_value,
        cell.raw_cached_value,
        cell.effective_value,
    ):
        if _is_non_finite(value):
            issues.append(
                _issue(
                    "NON_FINITE_SOURCE_VALUE",
                    IssueSeverity.ERROR,
                    "Исходное значение содержит NaN или Infinity",
                    cell.coordinate,
                )
            )
            break
    return issues


def validate_canonical_source_row(
    row: CanonicalSourceRow,
) -> tuple[RowValidationIssue, ...]:
    issues: list[RowValidationIssue] = []
    if not row.row_id:
        issues.append(_issue("ROW_ID_MISSING", IssueSeverity.ERROR, "Отсутствует row_id"))
    location = row.source_location
    if location.row_number < 1 or not location.sheet_name or not location.source_file_id:
        issues.append(
            _issue(
                "SOURCE_LOCATION_INVALID",
                IssueSeverity.ERROR,
                "Некорректное местоположение строки",
            )
        )

    for name in _NUMERIC_FIELDS:
        value = getattr(row, name)
        if value is not None and (not isinstance(value, Decimal) or not value.is_finite()):
            issues.append(
                _issue(
                    "NUMERIC_VALUE_INVALID",
                    IssueSeverity.ERROR,
                    f"Поле {name} должно быть конечным Decimal",
                )
            )

    for cell in row.source_values:
        issues.extend(_validate_coordinate(row, cell))
        if cell.provenance.logical_column != cell.logical_column:
            issues.append(
                _issue(
                    "LOGICAL_COLUMN_MISMATCH",
                    IssueSeverity.ERROR,
                    "Логический столбец не совпадает с provenance",
                    cell.coordinate,
                )
            )
        issues.extend(_validate_cell_state(cell))
        if cell.status == CellValueStatus.VALUE_READ_FAILED.value:
            issues.append(
                _issue(
                    "VALUE_READ_FAILED",
                    IssueSeverity.ERROR,
                    "Не удалось прочитать исходную ячейку",
                    cell.coordinate,
                )
            )
        elif cell.status in {
            CellValueStatus.EXCEL_ERROR.value,
            CellValueStatus.FORMULA_WITHOUT_CACHED_VALUE.value,
            CellValueStatus.UNSUPPORTED_VALUE_TYPE.value,
        }:
            issues.append(
                _issue(
                    cell.status,
                    IssueSeverity.WARNING,
                    f"Проблемное исходное значение: {cell.status}",
                    cell.coordinate,
                )
            )

    required_names = {"work_name", "name"}
    if row.source_type == "svvr":
        required_names.update({"current_period_quantity", "quantity"})
    for cell in row.source_values:
        if (
            cell.logical_column in required_names
            and cell.status == CellValueStatus.VALUE_READ_FAILED.value
        ):
            issues.append(
                _issue(
                    "REQUIRED_CELL_READ_FAILED",
                    IssueSeverity.ERROR,
                    f"Ошибка обязательной ячейки {cell.logical_column}",
                    cell.coordinate,
                )
            )
    return tuple(issues)
