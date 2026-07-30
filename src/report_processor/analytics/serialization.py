"""Canonical serialization and strict decimal validation for analytics."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any

from .exceptions import AnalyticalWriteError

_MAX_DECIMAL_SCALE = 18
_MAX_DECIMAL_INTEGER_DIGITS = 20


def deterministic_json(value: Any) -> str:
    return json.dumps(
        to_json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def payload_hash(value: Any) -> tuple[str, str]:
    payload_json = deterministic_json(value)
    return payload_json, sha256(payload_json.encode("utf-8")).hexdigest()


def target_row_id(
    target_source_id: str, target_fingerprint: str, sheet_name: str, row_number: int
) -> str:
    return sha256(
        f"{target_source_id}{target_fingerprint}{sheet_name}{row_number}".encode()
    ).hexdigest()


def strict_decimal(value: Decimal | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, Decimal):
        raise AnalyticalWriteError(f"{field_name} должен быть Decimal или null; float запрещён")
    if not value.is_finite():
        raise AnalyticalWriteError(f"{field_name} должен содержать конечный Decimal")
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int) or exponent < -_MAX_DECIMAL_SCALE:
        raise AnalyticalWriteError(f"{field_name} превышает scale DECIMAL(38,18)")
    integer_digits = 1 if value.is_zero() else max(value.adjusted() + 1, 0)
    if integer_digits > _MAX_DECIMAL_INTEGER_DIGITS:
        raise AnalyticalWriteError(f"{field_name} превышает precision DECIMAL(38,18)")
    return format(value, "f")


def to_json_value(value: Any) -> Any:
    if is_dataclass(value):
        return {key: to_json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, Decimal):
        return strict_decimal(value, field_name="payload decimal")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    if isinstance(value, tuple | list):
        return [to_json_value(item) for item in value]
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise AnalyticalWriteError("JSON payload допускает только строковые ключи")
        return {key: to_json_value(item) for key, item in value.items()}
    if isinstance(value, float):
        raise AnalyticalWriteError("float запрещён в analytical payload")
    if value is None or isinstance(value, str | int | bool):
        return value
    raise AnalyticalWriteError(
        f"Неподдерживаемое значение analytical payload: {type(value).__name__}"
    )
