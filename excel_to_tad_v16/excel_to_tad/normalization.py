"""Нормализация ячеек, безопасный парсинг типов и правила схемы."""

from __future__ import annotations

import math
import unicodedata
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from typing import Any

from .constants import (
    BOOLEAN_HEADER_MARKERS, FALSE_TEXT_VALUES, IDENTIFIER_INTEGER_TEXT_RE,
    NORMALIZATION_REPLACEMENTS, NORMALIZED_NON_WORD_RE,
    NUMERIC_HEADER_MARKERS, NUMERIC_MISSING_VALUES, PLACEHOLDER_VALUES,
    POSITIVE_INTEGER_RE, RUSSIAN_BOOLEAN_TEXT_VALUES,
    STRONG_TEXT_HEADER_MARKERS, STRUCTURAL_EMPTY_VALUES,
    TEXT_IDENTIFIER_HEADER_MARKERS, TRUE_TEXT_VALUES,
    VISUAL_LATIN_TO_CYRILLIC, WHITESPACE_RE,
)

def normalized(value: Any) -> str:
    """Нормализация текста для сопоставления заголовков."""
    if value is None:
        return ""

    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("\n", " ").replace("\r", " ")
    text = text.replace("ё", "е").replace("Ё", "Е").lower()
    text = text.translate(VISUAL_LATIN_TO_CYRILLIC)

    for pattern, replacement in NORMALIZATION_REPLACEMENTS:
        text = pattern.sub(replacement, text)

    text = NORMALIZED_NON_WORD_RE.sub(" ", text)
    return WHITESPACE_RE.sub(" ", text).strip()

def compact_normalized(value: Any) -> str:
    return WHITESPACE_RE.sub("", normalized(value))

def clean_text(value: Any) -> str | None:
    if value is None:
        return None

    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("\r", " ").replace("\n", " ")
    text = WHITESPACE_RE.sub(" ", text).strip()
    return text or None

def header_contains_marker(header: str, markers: set[str]) -> bool:
    norm = normalized(header)
    tokens = set(norm.split())
    return any(
        marker in norm if " " in marker else marker in tokens
        for marker in markers
    )

def is_text_identifier_header(header: str) -> bool:
    """Колонки идентификаторов, нумерации и этапов всегда остаются текстом."""
    if header_contains_marker(header, STRONG_TEXT_HEADER_MARKERS):
        return True
    if is_numeric_header(header):
        return False
    return header_contains_marker(header, TEXT_IDENTIFIER_HEADER_MARKERS)

def is_boolean_header(header: str) -> bool:
    return header_contains_marker(header, BOOLEAN_HEADER_MARKERS)

def is_numeric_header(header: str) -> bool:
    return header_contains_marker(header, NUMERIC_HEADER_MARKERS)

def is_placeholder(value: Any) -> bool:
    cleaned = clean_text(value)
    return cleaned is None or normalized(cleaned) in PLACEHOLDER_VALUES


def is_numeric_missing(value: Any) -> bool:
    """Пустой/служебный маркер, который не должен ломать числовой тип."""
    cleaned = clean_text(value)
    return cleaned is None or normalized(cleaned) in NUMERIC_MISSING_VALUES


def is_structural_empty(value: Any) -> bool:
    """Пустая ячейка или визуальный заполнитель строки: '.', '-', '…'."""
    cleaned = clean_text(value)
    return cleaned is None or normalized(cleaned) in STRUCTURAL_EMPTY_VALUES


def stringify_cell(value: Any) -> str | None:
    """Стабильное текстовое представление без потери кодов и ведущих нулей."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    return clean_text(value)


def stringify_identifier_cell(value: Any) -> str | None:
    """
    Текстовое представление номера/кода без искусственного суффикса ``.0``.

    Исходные строковые ведущие нули сохраняются: ``"001"`` остаётся
    ``"001"``. Дробные этапы и коды, например ``1.2``, остаются текстом.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        if value.is_integer():
            return str(int(value))
        return format(value, ".15g")

    text = clean_text(value)
    if text is None:
        return None
    compact = text.replace("\xa0", "").replace("\u202f", "").replace(" ", "")
    match = IDENTIFIER_INTEGER_TEXT_RE.fullmatch(compact)
    if match:
        sign, digits = match.groups()
        return f"{sign}{digits}"
    return text


def parse_boolean_value(
    value: Any,
    allow_numeric: bool,
) -> tuple[bool, bool | None]:
    """Возвращает ``(распознано, значение)`` для безопасных boolean-форм."""
    if value is None or clean_text(value) is None:
        return True, None
    if isinstance(value, bool):
        return True, value

    norm = normalized(value)
    if norm in TRUE_TEXT_VALUES:
        return True, True
    if norm in FALSE_TEXT_VALUES:
        return True, False

    # «Да/Нет» намеренно остаются текстом по согласованному правилу.
    if norm in RUSSIAN_BOOLEAN_TEXT_VALUES:
        return False, None

    if allow_numeric:
        number = to_float(value)
        if number == 1.0:
            return True, True
        if number == 0.0:
            return True, False

    return False, None

def infer_column_role(header: str, values: Sequence[Any]) -> str:
    """Определяет безопасный тип колонки без агрессивного приведения."""
    if is_text_identifier_header(header):
        return "text"

    nonempty = [value for value in values if clean_text(value) is not None]
    if not nonempty:
        return "text"

    if any(normalized(value) in RUSSIAN_BOOLEAN_TEXT_VALUES for value in nonempty):
        return "text"

    boolean_header = is_boolean_header(header)
    boolean_results = [
        parse_boolean_value(value, allow_numeric=boolean_header)[0]
        for value in nonempty
    ]
    if all(boolean_results):
        return "boolean"

    if all(isinstance(value, datetime) for value in nonempty):
        return "datetime"
    if all(
        isinstance(value, date) and not isinstance(value, datetime)
        for value in nonempty
    ):
        return "date"

    # Точки, тире, X и аналогичные служебные маркеры не должны превращать
    # фактически числовую колонку в String, даже если её заголовок вроде
    # «в отчётном периоде» сам по себе не содержит слова «количество».
    numeric_values = [
        value for value in nonempty if not is_numeric_missing(value)
    ]
    if numeric_values and all(to_float(value) is not None for value in numeric_values):
        return "float"

    return "text"

def stabilize_float_precision(number: float) -> float:
    """
    Убирает только хвост двоичного/формульного шума без фиксированного
    количества знаков после запятой.

    Например, ``80.810000000001`` становится ``80.81``, при этом значения
    ``0.8412``, ``1.42277`` и ``2288.0539`` сохраняют свою точность.
    """
    if number == 0.0:
        return 0.0

    # Ищем ближайшее десятичное представление от 0 до 12 знаков, но
    # принимаем его только при микроскопической разнице <= 1e-12.
    # Это не бизнес-округление до 2/3 знаков, а очистка артефакта float.
    for decimal_places in range(13):
        candidate = round(number, decimal_places)
        if abs(number - candidate) <= 1e-12:
            return float(candidate)
    return number


def to_float(value: Any) -> float | None:
    """Преобразует числовое значение Excel в конечный стабильный ``float``."""
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        number = float(value)
        return stabilize_float_precision(number) if math.isfinite(number) else None

    if isinstance(value, (date, datetime)):
        return None

    text = unicodedata.normalize("NFKC", str(value)).strip()
    if normalized(text) in PLACEHOLDER_VALUES:
        return None

    text = (
        text.replace("\xa0", "")
        .replace("\u202f", "")
        .replace(" ", "")
        .replace("'", "")
        .replace("руб.", "")
        .replace("руб", "")
        .replace("₽", "")
    )

    negative_in_parentheses = text.startswith("(") and text.endswith(")")
    if negative_in_parentheses:
        text = text[1:-1]

    is_percent = text.endswith("%")
    if is_percent:
        text = text[:-1]

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    else:
        text = text.replace(",", ".")

    try:
        number = float(text)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None
    if negative_in_parentheses:
        number = -number
    if is_percent:
        number /= 100.0

    return stabilize_float_precision(number)

def is_small_integer(value: Any) -> bool:
    number = to_float(value)
    return (
        number is not None
        and number.is_integer()
        and 0.0 <= number <= 500.0
    )

def positive_integer(value: Any) -> int | None:
    """
    Вернуть положительный целый порядковый номер.

    Поддерживаются: 1, 1.0, "1", "1.", "1)", "№ 1", "п. 1".
    """
    if isinstance(value, str):
        text = unicodedata.normalize("NFKC", value).strip().lower()
        text = text.replace("\xa0", " ").replace("\u202f", " ")
        match = POSITIVE_INTEGER_RE.fullmatch(text)
        if match:
            integer = int(match.group(1))
            return integer if integer > 0 else None

    number = to_float(value)
    if number is None or not number.is_integer():
        return None

    integer = int(number)
    return integer if integer > 0 else None

def make_unique_headers(
    values: Iterable[Any],
    count: int,
) -> list[str]:
    values_list = list(values)
    result: list[str] = []
    seen: dict[str, int] = {}

    for index in range(count):
        value = (
            values_list[index]
            if index < len(values_list)
            else ""
        )
        base = clean_text(value) or f"column_{index + 1}"

        number = seen.get(base, 0) + 1
        seen[base] = number

        result.append(
            base if number == 1 else f"{base}_{number}"
        )

    return result
