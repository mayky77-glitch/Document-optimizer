"""Fail-closed discovery of a reconciliation target's current-period pair."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import range_boundaries

_HEADER_ROWS = 80
_RUSSIAN_MONTH_TOKENS = {
    "январь": 1,
    "января": 1,
    "февраль": 2,
    "февраля": 2,
    "март": 3,
    "марта": 3,
    "апрель": 4,
    "апреля": 4,
    "май": 5,
    "мая": 5,
    "июнь": 6,
    "июня": 6,
    "июль": 7,
    "июля": 7,
    "август": 8,
    "августа": 8,
    "сентябрь": 9,
    "сентября": 9,
    "октябрь": 10,
    "октября": 10,
    "ноябрь": 11,
    "ноября": 11,
    "декабрь": 12,
    "декабря": 12,
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
class HistoricalTargetMeasureEvidence:
    """Immutable structural proof for one documentary insertion anchor."""

    sheet_name: str
    quantity_column: int
    cost_column: int
    parent_span: tuple[int, int, int, int]
    quantity_leaf_row: int
    cost_leaf_row: int
    quantity_leaf_label: str
    cost_leaf_label: str
    suffix_coordinates: tuple[str, ...]

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


def discover_historical_target_measures(
    workbook,
    first_detail_rows: dict[str, int],
    merged_ranges_by_sheet: dict[str, tuple[str, ...]] | None = None,
) -> tuple[HistoricalTargetMeasureEvidence, ...]:
    """Return one documentary/historical adjacent measure pair per selected sheet.

    This is deliberately separate from the current-period reader: a pair is an
    insertion anchor only when its header path positively says it is historical.
    """

    pairs: list[HistoricalTargetMeasureEvidence] = []
    for sheet_name, first_detail_row in sorted(first_detail_rows.items()):
        candidates = _sheet_historical_candidates(
            workbook[sheet_name],
            first_detail_row,
            (merged_ranges_by_sheet or {}).get(sheet_name, ()),
        )
        if len(candidates) != 1:
            raise ReconciliationTargetMeasureError("TARGET_HISTORICAL_PAIR_MISSING")
        pairs.append(candidates[0])
    if not pairs:
        raise ReconciliationTargetMeasureError("TARGET_HISTORICAL_PAIR_MISSING")
    return tuple(pairs)


def _sheet_candidates(
    sheet, first_detail_row: int, merged_ranges: tuple[str, ...]
) -> tuple[TargetMeasurePair, ...]:
    end = max(0, first_detail_row - 1)
    start = max(1, end - _HEADER_ROWS + 1)
    if end < start:
        return ()
    values, spans = _header_cells(sheet, start, end, merged_ranges)
    candidates: dict[tuple[object, ...], HistoricalTargetMeasureEvidence] = {}
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
            quantity_periods = _period_mentions(quantity_text)
            cost_periods = _period_mentions(cost_text)
            if _period_conflict(quantity_periods, cost_periods):
                continue
            same_period = _same_unambiguous_period(quantity_periods, cost_periods)
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


def _sheet_historical_candidates(
    sheet, first_detail_row: int, merged_ranges: tuple[str, ...]
) -> tuple[HistoricalTargetMeasureEvidence, ...]:
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
            if (
                not _quantity_leaf(quantity[-1].text)
                or not _total_cost_leaf(cost[-1].text)
                or _unit_price(quantity_text)
                or _unit_price(cost_text)
                or not _historical(quantity_text + " " + cost_text)
            ):
                continue
            common = [label for label in quantity if label.key in {item.key for item in cost}]
            parents = [label for label in common if label.key[1] != label.key[3]]
            if len(parents) != 1:
                continue
            suffix = tuple(
                f"{get_column_letter(column)}{row_number}"
                for row_number in range(1, int(sheet.max_row or 0) + 1)
                for column in range(cost_column + 1, int(sheet.max_column or 0) + 1)
                if sheet.cell(row_number, column).value is not None
            )
            if not suffix:
                continue
            key = (sheet.title, quantity_column, cost_column, parents[0].key)
            candidates[key] = HistoricalTargetMeasureEvidence(
                sheet.title,
                quantity_column,
                cost_column,
                parents[0].key,
                quantity[-1].key[0],
                cost[-1].key[0],
                str(sheet.cell(quantity[-1].key[0], quantity_column).value or ""),
                str(sheet.cell(cost[-1].key[0], cost_column).value or ""),
                suffix,
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
    return (
        any(stem in value for stem in ("истор", "документ", "накоп", "нараст", "предыдущ", "прошл"))
        or {"весь", "период"}.issubset(tokens)
        or ({"с", "начала"}.issubset(tokens))
        or any(token.startswith("итог") for token in tokens)
    )


def _current_scope(value: str) -> bool:
    return "период" in value and any(stem in value for stem in ("текущ", "отчетн", "отчётн"))


def _period_mentions(value: str) -> frozenset[tuple[int, int | None]]:
    result = {(int(month), int(year)) for year, month in _YEAR_MONTH.findall(value)}
    result.update((int(month), int(year)) for month, year in _MONTH_YEAR.findall(value))
    result.update((int(month), int(year)) for month, year in _DATE.findall(value))
    tokens = re.findall(r"\w+", value, flags=re.UNICODE)
    for index, token in enumerate(tokens):
        month = _RUSSIAN_MONTH_TOKENS.get(token)
        if month is None:
            continue
        next_token = tokens[index + 1] if index + 1 < len(tokens) else ""
        year = int(next_token) if _year(next_token) else None
        result.add((month, year))
    return frozenset(result)


def _same_unambiguous_period(
    quantity_periods: frozenset[tuple[int, int | None]],
    cost_periods: frozenset[tuple[int, int | None]],
) -> bool:
    return len(quantity_periods) == len(cost_periods) == 1 and quantity_periods == cost_periods


def _period_conflict(
    quantity_periods: frozenset[tuple[int, int | None]],
    cost_periods: frozenset[tuple[int, int | None]],
) -> bool:
    """Reject multiple or contradictory calendar evidence before parent fallback."""

    if len(quantity_periods) > 1 or len(cost_periods) > 1:
        return True
    return bool(quantity_periods and cost_periods and quantity_periods != cost_periods)


def _year(value: str) -> bool:
    return bool(re.fullmatch(r"(?:19|20)\d{2}", value))


def _text(value: object | None) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).replace("\u00a0", " ")
    return " ".join(re.sub(r"[^\w./-]+", " ", normalized, flags=re.UNICODE).casefold().split())
