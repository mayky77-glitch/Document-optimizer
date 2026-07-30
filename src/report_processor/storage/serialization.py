from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from report_processor.extraction.models import (
    CanonicalSourceRow,
    ExtractedCellValue,
    SourceLocation,
    ValueProvenance,
)

from .exceptions import StorageSchemaError


def to_json_compatible(value: Any) -> Any:
    """Match the established canonical-row JSONL representation."""
    if is_dataclass(value):
        return {key: to_json_compatible(item) for key, item in asdict(value).items()}
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    if isinstance(value, tuple | list):
        return [to_json_compatible(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_json_compatible(item) for key, item in value.items()}
    return value


def canonical_row_payload(row: CanonicalSourceRow) -> dict[str, Any]:
    payload = to_json_compatible(row)
    if not isinstance(payload, dict):  # Defensive: CanonicalSourceRow is a dataclass.
        raise StorageSchemaError("Каноническая строка не сериализовалась в объект JSON")
    source_values = payload.get("source_values")
    if not isinstance(source_values, list):
        raise StorageSchemaError("source_values канонической строки должен быть массивом")
    for source_value, serialized_value in zip(row.source_values, source_values, strict=True):
        if not isinstance(serialized_value, dict):
            raise StorageSchemaError("source_values канонической строки должен содержать объекты")
        for field_name in ("raw_formula_value", "raw_cached_value", "effective_value"):
            serialized_value[field_name] = _encode_temporal(getattr(source_value, field_name))
    return payload


def deterministic_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def canonical_row_from_payload(payload_json: str) -> CanonicalSourceRow:
    try:
        payload = json.loads(payload_json)
        if not isinstance(payload, dict):
            raise TypeError("ожидался JSON-объект")
        location = _location(payload["source_location"])
        source_values = tuple(_cell(value) for value in payload["source_values"])
        return CanonicalSourceRow(
            row_id=_required_text(payload, "row_id"),
            source_type=_required_text(payload, "source_type"),
            source_location=location,
            document_index=_optional_text(payload, "document_index"),
            document_period=_optional_text(payload, "document_period"),
            object_code_raw=_optional_text(payload, "object_code_raw"),
            object_name_raw=_optional_text(payload, "object_name_raw"),
            subobject_code_raw=_optional_text(payload, "subobject_code_raw"),
            subobject_name_raw=_optional_text(payload, "subobject_name_raw"),
            position_code_raw=_optional_text(payload, "position_code_raw"),
            work_name_raw=_optional_text(payload, "work_name_raw"),
            unit_raw=_optional_text(payload, "unit_raw"),
            contract_quantity=_decimal(payload, "contract_quantity"),
            current_period_quantity=_decimal(payload, "current_period_quantity"),
            cumulative_quantity=_decimal(payload, "cumulative_quantity"),
            remaining_quantity=_decimal(payload, "remaining_quantity"),
            unit_price=_decimal(payload, "unit_price"),
            contract_cost=_decimal(payload, "contract_cost"),
            current_period_cost=_decimal(payload, "current_period_cost"),
            cumulative_cost=_decimal(payload, "cumulative_cost"),
            total_cost=_decimal(payload, "total_cost"),
            basis_code_raw=_optional_text(payload, "basis_code_raw"),
            drawing_code_raw=_optional_text(payload, "drawing_code_raw"),
            cost_type_code_raw=_optional_text(payload, "cost_type_code_raw"),
            source_values=source_values,
            status=_required_text(payload, "status"),
            warnings=_string_tuple(payload.get("warnings", [])),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise StorageSchemaError(f"Некорректная сохранённая каноническая строка: {exc}") from exc


def _location(value: Any) -> SourceLocation:
    if not isinstance(value, dict):
        raise TypeError("source_location должен быть объектом")
    return SourceLocation(
        source_file_id=_required_text(value, "source_file_id"),
        filename=_required_text(value, "filename"),
        sheet_name=_required_text(value, "sheet_name"),
        sheet_type=_required_text(value, "sheet_type"),
        row_number=_required_int(value, "row_number"),
        column_number=_optional_int(value, "column_number"),
        column_letter=_optional_text(value, "column_letter"),
        coordinate=_optional_text(value, "coordinate"),
    )


def _cell(value: Any) -> ExtractedCellValue:
    if not isinstance(value, dict):
        raise TypeError("source_values должен содержать объекты")
    provenance = value["provenance"]
    if not isinstance(provenance, dict):
        raise TypeError("provenance должен быть объектом")
    return ExtractedCellValue(
        logical_column=_required_text(value, "logical_column"),
        coordinate=_required_text(value, "coordinate"),
        raw_formula_value=_decode_temporal(value.get("raw_formula_value")),
        raw_cached_value=_decode_temporal(value.get("raw_cached_value")),
        effective_value=_decode_temporal(value.get("effective_value")),
        effective_value_source=_required_text(value, "effective_value_source"),
        formula_data_type=_optional_text(value, "formula_data_type"),
        cached_data_type=_optional_text(value, "cached_data_type"),
        is_formula=_required_bool(value, "is_formula"),
        is_empty=_required_bool(value, "is_empty"),
        is_error=_required_bool(value, "is_error"),
        status=_required_text(value, "status"),
        warnings=_string_tuple(value.get("warnings", [])),
        provenance=ValueProvenance(
            location=_location(provenance["location"]),
            logical_column=_required_text(provenance, "logical_column"),
            header_text=_optional_text(provenance, "header_text"),
            formula=_optional_text(provenance, "formula"),
            cached_value_available=_required_bool(provenance, "cached_value_available"),
            value_source=_required_text(provenance, "value_source"),
            warnings=_string_tuple(provenance.get("warnings", [])),
        ),
    )


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = payload[key]
    if not isinstance(value, str):
        raise TypeError(f"{key} должен быть строкой")
    return value


def _optional_text(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is not None and not isinstance(value, str):
        raise TypeError(f"{key} должен быть строкой или null")
    return value


def _required_int(payload: dict[str, Any], key: str) -> int:
    value = payload[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{key} должен быть целым")
    return value


def _optional_int(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
        raise TypeError(f"{key} должен быть целым или null")
    return value


def _required_bool(payload: dict[str, Any], key: str) -> bool:
    value = payload[key]
    if not isinstance(value, bool):
        raise TypeError(f"{key} должен быть bool")
    return value


def _decimal(payload: dict[str, Any], key: str) -> Decimal | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{key} должен быть decimal-строкой или null")
    return Decimal(value)


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise TypeError("ожидался массив строк")
    return tuple(value)


def _encode_temporal(value: Any) -> Any:
    if isinstance(value, datetime):
        return {"$storage_temporal": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"$storage_temporal": "date", "value": value.isoformat()}
    if isinstance(value, time):
        return {"$storage_temporal": "time", "value": value.isoformat()}
    return to_json_compatible(value)


def _decode_temporal(value: Any) -> Any:
    if not isinstance(value, dict) or set(value) != {"$storage_temporal", "value"}:
        return value
    kind = value["$storage_temporal"]
    iso_value = value["value"]
    if not isinstance(kind, str) or not isinstance(iso_value, str):
        return value
    try:
        if kind == "datetime":
            return datetime.fromisoformat(iso_value)
        if kind == "date":
            return date.fromisoformat(iso_value)
        if kind == "time":
            return time.fromisoformat(iso_value)
    except ValueError as exc:
        raise StorageSchemaError(f"Некорректное temporal provenance значение: {exc}") from exc
    return value
