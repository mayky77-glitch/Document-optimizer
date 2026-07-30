from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from report_processor.extraction.models import ExtractedCellValue
from report_processor.extraction.numeric_values import parse_decimal_value
from report_processor.extraction.statuses import (
    CellValueStatus,
    NumericValueStatus,
    TextValueStatus,
)
from report_processor.extraction.text_values import parse_text_value


def find_cell(
    values: tuple[ExtractedCellValue, ...],
    *logical_names: str,
) -> ExtractedCellValue | None:
    for logical_name in logical_names:
        for value in values:
            if value.logical_column == logical_name:
                return value
    return None


def parse_text_cell(
    values: tuple[ExtractedCellValue, ...],
    *logical_names: str,
) -> tuple[str | None, tuple[str, ...]]:
    cell = find_cell(values, *logical_names)
    if cell is None:
        return None, ()
    parsed = parse_text_value(cell.effective_value)
    warnings = list(cell.warnings)
    if parsed.status not in {TextValueStatus.OK.value, TextValueStatus.EMPTY.value}:
        warnings.extend(f"{cell.coordinate}:{warning}" for warning in parsed.warnings)
    return parsed.value, tuple(warnings)


def parse_numeric_cell(
    values: tuple[ExtractedCellValue, ...],
    *logical_names: str,
) -> tuple[Decimal | None, tuple[str, ...]]:
    cell = find_cell(values, *logical_names)
    if cell is None:
        return None, ()
    parsed = parse_decimal_value(cell.effective_value)
    warnings = list(cell.warnings)
    if parsed.status not in {NumericValueStatus.OK.value, NumericValueStatus.EMPTY.value}:
        warnings.append(f"{cell.coordinate}:{parsed.status}")
        warnings.extend(f"{cell.coordinate}:{warning}" for warning in parsed.warnings)
    return parsed.value, tuple(warnings)


def cell_problem_warnings(values: Iterable[ExtractedCellValue]) -> tuple[str, ...]:
    warnings: list[str] = []
    for value in values:
        if value.status in {
            CellValueStatus.FORMULA_WITHOUT_CACHED_VALUE.value,
            CellValueStatus.EXCEL_ERROR.value,
            CellValueStatus.UNSUPPORTED_VALUE_TYPE.value,
            CellValueStatus.VALUE_READ_FAILED.value,
        }:
            warnings.append(f"{value.coordinate}:{value.status}")
    return tuple(dict.fromkeys(warnings))


def merge_warnings(*warning_groups: Iterable[str]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in warning_groups:
        merged.extend(group)
    return tuple(dict.fromkeys(merged))
