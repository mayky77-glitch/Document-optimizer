"""Потоковое чтение XLSB через pyxlsb."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import CachedWorksheet
from ..normalization import clean_text

def _xlsb_cell_value(cell: Any) -> Any:
    """Возвращает значение ячейки pyxlsb с поддержкой API 1.0/1.1."""
    try:
        is_date_formatted = bool(getattr(cell, "is_date_formatted", False))
    except Exception:
        is_date_formatted = False

    if is_date_formatted:
        try:
            date_value = getattr(cell, "date_value", None)
        except Exception:
            date_value = None
        if date_value is not None:
            return date_value

    if hasattr(cell, "value"):
        return cell.value
    return getattr(cell, "v", None)

def _xlsb_zero_based_row(cell: Any) -> int | None:
    """Извлекает нулевой индекс строки из разных версий pyxlsb."""
    for attribute in ("row_num", "r"):
        try:
            value = getattr(cell, attribute)
        except (AttributeError, TypeError, ValueError):
            continue
        if value is not None:
            return int(value)
    return None

def _xlsb_zero_based_column(cell: Any) -> int | None:
    """Извлекает нулевой индекс колонки из разных версий pyxlsb."""
    for attribute in ("col", "c"):
        try:
            value = getattr(cell, attribute)
        except (AttributeError, TypeError, ValueError):
            continue
        if value is not None:
            return int(value)
    return None

def cache_xlsb_worksheet(worksheet: Any, title: str) -> CachedWorksheet:
    """
    Читает лист XLSB один раз через pyxlsb и приводит его к общему кэшу.

    pyxlsb возвращает нулевые индексы строк и колонок. Формулы не
    вычисляются Python-кодом: используются результаты, сохранённые Excel
    внутри книги. Для pyxlsb 1.1+ даты с распознанным форматом переводятся
    в datetime; в pyxlsb 1.0 неразмеченные даты могут остаться числами Excel.
    """
    rows: dict[int, dict[int, Any]] = {}
    actual_max_row = 0
    actual_max_column = 0

    for source_row in worksheet.rows(sparse=True):
        sparse: dict[int, Any] = {}
        excel_row_number: int | None = None

        for cell in source_row:
            value = _xlsb_cell_value(cell)
            if clean_text(value) is None:
                continue

            zero_based_column = _xlsb_zero_based_column(cell)
            if zero_based_column is None:
                continue

            zero_based_row = _xlsb_zero_based_row(cell)
            if zero_based_row is not None:
                excel_row_number = zero_based_row + 1

            column_number = zero_based_column + 1
            sparse[column_number] = value
            actual_max_column = max(actual_max_column, column_number)

        if not sparse:
            continue

        if excel_row_number is None:
            row_index = getattr(source_row, "num", None)
            if row_index is None:
                raise RuntimeError(
                    "pyxlsb не вернул номер строки для непустой строки листа."
                )
            excel_row_number = int(row_index) + 1

        rows[excel_row_number] = sparse
        actual_max_row = max(actual_max_row, excel_row_number)

    return CachedWorksheet(
        title=title,
        rows=rows,
        max_row=actual_max_row,
        max_column=actual_max_column,
    )

def cache_xlsb_workbook_sheet(workbook: Any, sheet_name: str) -> CachedWorksheet:
    """Открывает один лист XLSB, кэширует значения и сразу закрывает лист."""
    getter = getattr(workbook, "get_sheet_by_name", None)
    worksheet = (
        getter(sheet_name)
        if callable(getter)
        else workbook.get_sheet(sheet_name)
    )
    try:
        return cache_xlsb_worksheet(worksheet, sheet_name)
    finally:
        close = getattr(worksheet, "close", None)
        if callable(close):
            close()


def open_xlsb_workbook(path: Path) -> tuple[Any, list[str]]:
    """Открывает XLSB и возвращает книгу со списком листов."""
    try:
        from pyxlsb import open_workbook
    except ImportError as exc:
        raise RuntimeError(
            "Для чтения .xlsb не установлен pyxlsb. Выполните:\n"
            "python3 -m pip install --upgrade pyxlsb"
        ) from exc

    workbook = open_workbook(str(path))
    return workbook, list(workbook.sheets)
