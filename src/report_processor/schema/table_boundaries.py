"""Approximate data start and horizontal table bounds only."""

from __future__ import annotations

import re

from report_processor.schema.models import ColumnResolution, ComposedHeader, WorksheetScanWindow

_HEADER_WORDS = {
    "наименование",
    "количество",
    "стоимость",
    "единица",
    "измерения",
    "объект",
    "позиция",
    "период",
}


def _row_cells(scan: WorksheetScanWindow, row: int) -> list[object]:
    return [cell.raw_value for cell in scan.cells if cell.row == row and not cell.is_empty]


_NUMBER = re.compile(r"^\d+(?:[.,]\d+)?$")
_CHAINED_NUMBER = re.compile(r"^=[A-Z]+\d+\+1$", re.IGNORECASE)
_HIDE_MARKERS = {"скрыть", "скрывается"}


def _looks_like_numbering_row(values: list[object]) -> bool:
    """Recognize control labels without treating ordinary mixed data as numbering."""

    if len(values) < 2:
        return False
    numeric_signals = 0
    hide_signal = False
    for value in values:
        if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 500:
            numeric_signals += 1
        elif isinstance(value, str):
            normalized = value.strip().casefold().replace("ё", "е")
            if normalized in _HIDE_MARKERS:
                hide_signal = True
            elif (
                _NUMBER.fullmatch(normalized) and float(normalized.replace(",", ".")) <= 500
            ) or _CHAINED_NUMBER.fullmatch(normalized):
                numeric_signals += 1
            else:
                return False
        else:
            return False
    return numeric_signals >= 2 and (numeric_signals == len(values) or hide_signal)


def _looks_like_data(values: list[object]) -> bool:
    if not values or _looks_like_numbering_row(values):
        return False
    numeric = sum(
        isinstance(value, (int, float)) and not isinstance(value, bool) for value in values
    )
    texts = [
        str(value).strip() for value in values if isinstance(value, str) and str(value).strip()
    ]
    corpus = " ".join(text.lower().replace("ё", "е") for text in texts)
    header_hits = len(_HEADER_WORDS.intersection(corpus.split()))
    if header_hits >= 3 and numeric == 0:
        return False
    if numeric and texts:
        return True
    return len(texts) >= 2 and any(any(char.isdigit() for char in text) for text in texts)


def detect_data_start_row(
    scan: WorksheetScanWindow,
    *,
    header_end_row: int,
    max_gap_rows: int = 3,
) -> int | None:
    empty_rows = 0
    max_row = min(scan.max_scanned_row, header_end_row + max_gap_rows + 5)
    for row in range(header_end_row + 1, max_row + 1):
        values = _row_cells(scan, row)
        if not values:
            empty_rows += 1
            if empty_rows > max_gap_rows:
                return None
            continue
        if _looks_like_data(values):
            return row
    return None


def _clusters(columns: list[int], max_gap: int = 3) -> list[list[int]]:
    if not columns:
        return []
    result = [[columns[0]]]
    for column in columns[1:]:
        if column - result[-1][-1] <= max_gap:
            result[-1].append(column)
        else:
            result.append([column])
    return result


def detect_table_column_bounds(
    headers: tuple[ComposedHeader, ...],
    columns: tuple[ColumnResolution, ...],
) -> tuple[int | None, int | None]:
    nonempty = sorted(header.column_index for header in headers if not header.is_empty)
    resolved = sorted(
        resolution.column_index
        for resolution in columns
        if resolution.status == "OK" and resolution.column_index is not None
    )
    if resolved:
        lower, upper = min(resolved), max(resolved)
        supporting = [column for column in nonempty if lower - 3 <= column <= upper + 3]
        if supporting:
            lower, upper = min(supporting), max(supporting)
        return lower, upper
    clusters = _clusters(nonempty)
    if not clusters:
        return None, None
    best = max(clusters, key=lambda item: (len(item), -item[0]))
    return min(best), max(best)
