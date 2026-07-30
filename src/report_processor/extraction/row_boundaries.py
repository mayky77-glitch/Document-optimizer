from __future__ import annotations

import re
import unicodedata
from decimal import Decimal

from report_processor.schema import LogicalColumn, WorksheetSchema

from .models import ExtractedCellValue
from .statuses import CellValueStatus, EffectiveValueSource

_NUMERIC_KEYS = {
    LogicalColumn.CONTRACT_QUANTITY.value,
    LogicalColumn.CURRENT_PERIOD_QUANTITY.value,
    LogicalColumn.CUMULATIVE_QUANTITY.value,
    LogicalColumn.REMAINING_QUANTITY.value,
    LogicalColumn.UNIT_PRICE.value,
    LogicalColumn.CONTRACT_COST.value,
    LogicalColumn.CURRENT_PERIOD_COST.value,
    LogicalColumn.CUMULATIVE_COST.value,
    LogicalColumn.TOTAL_COST.value,
}


def _normalized(value: object) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    text = text.replace("ё", "е").replace("\u00a0", " ").replace("\u202f", " ")
    return re.sub(r"[^\wа-я]+", " ", text).strip()


def _is_contentful(
    value: ExtractedCellValue,
    *,
    include_formula_without_cache: bool,
) -> bool:
    if value.effective_value_source == EffectiveValueSource.FORMULA_WITHOUT_CACHE.value:
        return include_formula_without_cache
    if value.status in {
        CellValueStatus.EXCEL_ERROR.value,
        CellValueStatus.VALUE_READ_FAILED.value,
    }:
        return True
    effective = value.effective_value
    if effective is None:
        return False
    if isinstance(effective, bool):
        return True
    if isinstance(effective, (int, float, Decimal)):
        return True
    if isinstance(effective, str):
        return bool(effective.strip())
    return True


def is_effectively_empty_row(
    values: tuple[ExtractedCellValue, ...],
    *,
    key_columns: tuple[LogicalColumn, ...],
    include_formula_without_cache: bool = True,
) -> bool:
    key_names = {item.value for item in key_columns}
    selected = [value for value in values if value.logical_column in key_names]
    if not selected:
        selected = list(values)
    return not any(
        _is_contentful(
            value,
            include_formula_without_cache=include_formula_without_cache,
        )
        for value in selected
    )


def looks_like_repeated_header(
    values: tuple[ExtractedCellValue, ...],
    schema: WorksheetSchema,
) -> bool:
    non_empty = [value for value in values if _normalized(value.effective_value)]
    if len(non_empty) < 2:
        return False

    headers = {
        item.logical_column.value: _normalized(item.header_text)
        for item in schema.columns
        if item.header_text
    }
    matches = 0
    numeric_word_hits = 0
    text_count = 0
    for value in non_empty:
        normalized = _normalized(value.effective_value)
        if isinstance(value.effective_value, str):
            text_count += 1
        header = headers.get(value.logical_column, "")
        if header and (normalized == header or normalized in header or header in normalized):
            matches += 1
        if value.logical_column in _NUMERIC_KEYS and any(
            token in normalized for token in ("количество", "стоимость", "цена", "объем")
        ):
            numeric_word_hits += 1

    majority_text = text_count / len(non_empty) >= 0.7
    enough_matches = matches >= max(2, len(non_empty) // 2)
    return majority_text and (enough_matches or numeric_word_hits >= 1)


def default_key_columns(plan_columns: tuple[LogicalColumn, ...]) -> tuple[LogicalColumn, ...]:
    preferred = (
        LogicalColumn.WORK_NAME,
        LogicalColumn.POSITION_CODE,
        LogicalColumn.CONTRACT_QUANTITY,
        LogicalColumn.CURRENT_PERIOD_QUANTITY,
        LogicalColumn.CUMULATIVE_QUANTITY,
        LogicalColumn.REMAINING_QUANTITY,
        LogicalColumn.UNIT_PRICE,
        LogicalColumn.CONTRACT_COST,
        LogicalColumn.CURRENT_PERIOD_COST,
        LogicalColumn.CUMULATIVE_COST,
        LogicalColumn.TOTAL_COST,
    )
    available = set(plan_columns)
    selected = tuple(item for item in preferred if item in available)
    return selected or plan_columns
