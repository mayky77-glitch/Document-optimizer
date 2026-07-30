from __future__ import annotations

import math
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from .models import ParsedNumericValue
from .statuses import NumericValueStatus

_EMPTY_MARKERS = {"", "—", "–", "-"}
_INVALID_MARKERS = {"n/a", "na", "нет", "#name?", "#n/a"}
_TEXT_NUMBER_RE = re.compile(r"^[+-]?(?:\d{1,3}(?: \d{3})+|\d+)(?:[.,]\d+)?$")


def _result(
    raw: object,
    value: Decimal | None,
    status: NumericValueStatus,
    *warnings: str,
) -> ParsedNumericValue:
    return ParsedNumericValue(
        raw_value=raw,
        value=value,
        status=status.value,
        warnings=tuple(warnings),
    )


def _from_decimal(raw: object, value: Decimal) -> ParsedNumericValue:
    if not value.is_finite():
        return _result(raw, None, NumericValueStatus.NON_FINITE, "NON_FINITE_NUMBER")
    return _result(raw, value, NumericValueStatus.OK)


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value)
    text = text.replace("\u00a0", " ").replace("\u202f", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_decimal_value(
    value: object,
    *,
    allow_text_numbers: bool = True,
) -> ParsedNumericValue:
    if value is None:
        return _result(value, None, NumericValueStatus.EMPTY)
    if isinstance(value, bool):
        return _result(value, None, NumericValueStatus.UNSUPPORTED_VALUE_TYPE, "BOOL_IS_NOT_NUMBER")
    if isinstance(value, (datetime, date)):
        return _result(value, None, NumericValueStatus.UNSUPPORTED_VALUE_TYPE, "DATE_IS_NOT_NUMBER")
    if isinstance(value, Decimal):
        return _from_decimal(value, value)
    if isinstance(value, int):
        return _from_decimal(value, Decimal(value))
    if isinstance(value, float):
        if not math.isfinite(value):
            return _result(value, None, NumericValueStatus.NON_FINITE, "NON_FINITE_NUMBER")
        return _from_decimal(value, Decimal(str(value)))
    if not isinstance(value, str):
        return _result(
            value,
            None,
            NumericValueStatus.UNSUPPORTED_VALUE_TYPE,
            f"UNSUPPORTED_VALUE_TYPE:{type(value).__name__}",
        )

    text = _normalize_text(value)
    folded = text.casefold()
    if folded in _EMPTY_MARKERS:
        return _result(value, None, NumericValueStatus.EMPTY)
    if folded in _INVALID_MARKERS:
        return _result(
            value,
            None,
            NumericValueStatus.INVALID_FORMAT,
            "NON_NUMERIC_MARKER",
        )
    if not allow_text_numbers:
        return _result(value, None, NumericValueStatus.TEXT_NUMBERS_DISABLED)
    if "," in text and "." in text:
        return _result(
            value,
            None,
            NumericValueStatus.INVALID_FORMAT,
            "AMBIGUOUS_DECIMAL_SEPARATORS",
        )
    if not _TEXT_NUMBER_RE.fullmatch(text):
        return _result(value, None, NumericValueStatus.INVALID_FORMAT, "INVALID_NUMBER_FORMAT")

    integer_part = re.split(r"[.,]", text, maxsplit=1)[0].lstrip("+-")
    if " " in integer_part:
        groups = integer_part.split(" ")
        if len(groups[0]) not in {1, 2, 3} or any(len(group) != 3 for group in groups[1:]):
            return _result(value, None, NumericValueStatus.INVALID_FORMAT, "INVALID_GROUPING")
    normalized = text.replace(" ", "").replace(",", ".")
    try:
        parsed = Decimal(normalized)
    except InvalidOperation:
        return _result(value, None, NumericValueStatus.INVALID_FORMAT, "DECIMAL_PARSE_FAILED")
    return _from_decimal(value, parsed)
