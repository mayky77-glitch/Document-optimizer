"""Лёгкие модели для разреженного представления Excel-листа."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CachedCell:
    value: Any

class CachedWorksheet:
    """
    Разреженный кэш значений одного листа.

    Он повторяет минимальную часть интерфейса openpyxl Worksheet, которую
    использует конвертер, но обращение к cell() выполняется за O(1) и не
    перечитывает XML-файл. В памяти хранится только текущий лист и только
    ячейки с реальными значениями, а не форматированный пустой диапазон.
    """

    __slots__ = ("_rows", "max_column", "max_row", "title")

    def __init__(
        self,
        title: str,
        rows: dict[int, dict[int, Any]],
        max_row: int,
        max_column: int,
    ) -> None:
        self.title = title
        self._rows = rows
        self.max_row = max_row
        self.max_column = max_column

    def cell(self, row: int, column: int) -> CachedCell:
        return CachedCell(self._rows.get(row, {}).get(column))

    def iter_rows(
        self,
        min_row: int = 1,
        max_row: int | None = None,
        min_col: int = 1,
        max_col: int | None = None,
        values_only: bool = False,
    ) -> Iterator[tuple[Any, ...]]:
        final_row = self.max_row if max_row is None else min(max_row, self.max_row)
        final_col = (
            self.max_column
            if max_col is None
            else min(max_col, self.max_column)
        )

        if final_row < min_row or final_col < min_col:
            return

        for row_number in range(min_row, final_row + 1):
            sparse = self._rows.get(row_number, {})
            values = tuple(
                sparse.get(column_number)
                for column_number in range(min_col, final_col + 1)
            )
            if values_only:
                yield values
            else:
                yield tuple(CachedCell(value) for value in values)
