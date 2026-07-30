"""Small deterministic JSON boundary shared by CLI adapters."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from report_processor.report_serialization import save_inspection_report


def json_value(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: json_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key.value if isinstance(key, Enum) else key): json_value(item)
            for key, item in value.items()
        }
    return value


def write_json(value: Any, output: Path) -> None:
    converted = json_value(value)
    if not isinstance(converted, dict):
        raise TypeError("Корень CLI JSON должен быть объектом")
    save_inspection_report(converted, output)
