"""Fail-closed discovery of a reconciliation target's current-period pair."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import range_boundaries

_HEADER_ROWS = 80
_MONTHS = {
    "январ": 1,
    "феврал": 2,
    "март": 3,
    "апрел": 4,
    "ма": 5,
    "июн": 6,
    "июл": 7,
    "август": 8,
    "сентябр": 9,
    "октябр": 10,
    "ноябр": 11,
    "декабр": 12,
}
_YEAR_MONTH = re.compile(r"(?<!\d)((?:19|20)\d{2})\s*[-./]\s*(0?[1-9]|1[0-2])(?!\d)")
_MONTH_YEAR = re.compile(r"(?<!\d)(0?[1-9]|1[0-2])\s*[./-]\s*((?:19|20)\d{2})(?!\d)")
_DATE = re.compile(r"(?<!\d)\d{1,2}\s*[./-]\s*(0?[1-9]|1[0-2])\s*[./-]\s*((?:19|20)\d{2})(?!\d)")


class ReconciliationTargetMeasureError(ValueError):
    """The selected target does not expose one safe current-period measure."""


@dataclass(frozen=True, slots=True)
class TargetMeasurePair:
    """One sheet-local quantity/total-cost pair with its header provenance."""

    sheet_name: str
    quantity_column: int
    cost_column: int
    quantity_header: str
    cost_header: str

    @property
    def quantity_letter(self) -> str:
        return get_column_letter(self.quantity_column)

    @property
    def cost_letter(self) -> str:
        return get_column_letter(self.cost_column)


@dataclass(frozen=True, slots=True)
class _Label:
    text: str
    key: tuple[int, int, int, int]


def discover_target_measures(
    workbook,
    first_detail_rows: dict[str, int],
    merged_ranges_by_sheet: dict[str, tuple[str, ...]] | None = None,
) -> tuple[TargetMeasurePair, ...]:
    """Discover exactly one current-period pair for every selected-stage sheet.

    The detector intentionally considers only the header immediately above a
    sheet's first semantic detail row.  It never uses a physical column as a
    fallback: an absent or competing structure is a controlled technical
    condition.
    """

    pairs: list[TargetMeasurePair] = []
    for sheet_name, first_detail_row in sorted(first_detail_rows.items()):
        candidates = _sheet_candidates(
            workbook[sheet_name],
            first_detail_row,
            (merged_ranges_by_sheet or {}).get(sheet_name, ()),
        )
        if not candidates:
            raise ReconciliationTargetMeasureError("TARGET_CURRENT_PERIOD_PAIR_MISSING")
        if len(candidates) != 1:
            raise ReconciliationTargetMeasureError("TARGET_CURRENT_PERIOD_PAIR_AMBIGUOUS")
        pairs.append(candidates[0])
    if not pairs:
        raise ReconciliationTargetMeasureError("TARGET_CURRENT_PERIOD_PAIR_MISSING")
    return tuple(pairs)


def _sheet_candidates(
    sheet, first_detail_row: int, merged_ranges: tuple[str, ...]
) -> tuple[TargetMeasurePair, ...]:
    end = max(0, first_detail_row - 1)
    start = max(1, end - _HEADER_ROWS + 1)
    if end < start:
        return ()
    values, spans = _header_cells(sheet, start, end, merged_ranges)
    candidates: dict[tuple[object, ...], TargetMeasurePair] = {}
    for row in range(start, end + 1):
        for quantity_column in range(1, int(sheet.max_column or 0)):
            cost_column = quantity_column + 1
            quantity = _labels(values, spans, start, row, quantity_column)
            cost = _labels(values, spans, start, row, cost_column)
            if (
                not quantity
                or not cost
                or not _leaf_at_row(quantity, row)
                or not _leaf_at_row(cost, row)
            ):
                continue
            quantity_text = " ".join(label.text for label in quantity)
            cost_text = " ".join(label.text for label in cost)
            if not _quantity_leaf(quantity[-1].text) or not _total_cost_leaf(cost[-1].text):
                continue
            if (
                _unit_price(quantity_text)
                or _unit_price(cost_text)
                or _historical(quantity_text + " " + cost_text)
            ):
                continue
            common = {label.key for label in quantity} & {label.key for label in cost}
            common_labels = tuple(
                label for label in quantity if label.key in common and label.key[1] != label.key[3]
            )
            common_current = any(_current_scope(label.text) for label in common_labels)
            quantity_periods = _periods(quantity_text)
            cost_periods = _periods(cost_text)
            same_period = (
                len(quantity_periods) == len(cost_periods) == 1 and quantity_periods == cost_periods
            )
            if not common_current and not same_period:
                continue
            key = (
                sheet.title,
                quantity_column,
                cost_column,
                quantity[-1].key,
                cost[-1].key,
            )
            candidates[key] = TargetMeasurePair(
                sheet.title,
                quantity_column,
                cost_column,
                quantity_text,
                cost_text,
            )
    return tuple(candidates.values())


def _header_cells(sheet, start: int, end: int, merged_ranges: tuple[str, ...]):
    values = {
        (row, column): sheet.cell(row, column).value
        for row in range(start, end + 1)
        for column in range(1, int(sheet.max_column or 0) + 1)
    }
    spans: dict[tuple[int, int], tuple[int, int, int, int]] = {}
    ranges = getattr(getattr(sheet, "merged_cells", None), "ranges", ())
    ranges = ranges or tuple(range_boundaries(item) for item in merged_ranges)
    for merged in ranges:
        if isinstance(merged, tuple):
            left, top, right, bottom = merged
        else:
            top, left, bottom, right = (
                merged.min_row,
                merged.min_col,
                merged.max_row,
                merged.max_col,
            )
        if bottom < start or top > end:
            continue
        key = (top, left, bottom, right)
        value = sheet.cell(top, left).value
        for row in range(max(start, top), min(end, bottom) + 1):
            for column in range(left, right + 1):
                values[row, column] = value
                spans[row, column] = key
    return values, spans


def _labels(values, spans, start: int, row: int, column: int) -> tuple[_Label, ...]:
    labels: list[_Label] = []
    seen: set[tuple[int, int, int, int]] = set()
    for header_row in range(start, row + 1):
        value = values.get((header_row, column))
        text = _text(value)
        if not text:
            continue
        key = spans.get((header_row, column), (header_row, column, header_row, column))
        if key not in seen:
            seen.add(key)
            labels.append(_Label(text, key))
    return tuple(labels)


def _leaf_at_row(labels: tuple[_Label, ...], row: int) -> bool:
    return bool(labels) and labels[-1].key[0] == row


def _quantity_leaf(value: str) -> bool:
    return any(stem in value for stem in ("колич", "объем", "объём"))


def _total_cost_leaf(value: str) -> bool:
    return any(stem in value for stem in ("стоим", "сумм", "затрат")) and not _unit_price(value)


def _unit_price(value: str) -> bool:
    return any(stem in value for stem in ("цен", "тариф", "расцен", "единиц"))


def _historical(value: str) -> bool:
    tokens = set(value.split())
    return any(
        stem in value for stem in ("истор", "документ", "накоп", "нараст", "предыдущ", "прошл")
    ) or bool({"весь", "всего", "итог"}.intersection(tokens))


def _current_scope(value: str) -> bool:
    return "период" in value and any(stem in value for stem in ("текущ", "отчетн", "отчётн"))


def _periods(value: str) -> frozenset[str]:
    result = {f"{year}-{int(month):02d}" for year, month in _YEAR_MONTH.findall(value)}
    result.update(f"{year}-{int(month):02d}" for month, year in _MONTH_YEAR.findall(value))
    result.update(f"{year}-{int(month):02d}" for month, year in _DATE.findall(value))
    for stem, month in _MONTHS.items():
        match = re.search(rf"\b{stem}\w*\s+((?:19|20)\d{{2}})\b", value)
        if match:
            result.add(f"{match.group(1)}-{month:02d}")
    return frozenset(result)


def _text(value: object | None) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).replace("\u00a0", " ")
    return " ".join(re.sub(r"[^\w./-]+", " ", normalized, flags=re.UNICODE).casefold().split())
