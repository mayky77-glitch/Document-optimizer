from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from report_processor.training_data.models import (
    DataQualityStatus,
    FormulaErrorCode,
    TrainingDataRow,
)

from .models import NormalizedBusinessKey, NormalizedSourceRow

_DECIMAL_FIELDS = (
    "contract_quantity",
    "period_quantity",
    "cumulative_quantity",
    "remaining_quantity",
    "unit_price",
    "contract_cost",
    "period_cost",
    "cumulative_cost",
    "total_cost",
)


def training_row_from_payload(payload: dict[str, Any]) -> TrainingDataRow:
    values = dict(payload)
    for field_name in _DECIMAL_FIELDS:
        value = values.get(field_name)
        if value is not None:
            decimal_value = Decimal(value)
            if not decimal_value.is_finite():
                raise ValueError(f"Поле {field_name} должно быть конечным Decimal")
            values[field_name] = decimal_value
    values["formula_error"] = FormulaErrorCode(values["formula_error"])
    values["data_quality_status"] = DataQualityStatus(values["data_quality_status"])
    values["warnings"] = tuple(values.get("warnings", ()))
    return TrainingDataRow(**values)


def load_training_rows_jsonl(path: Path) -> tuple[TrainingDataRow, ...]:
    rows: list[TrainingDataRow] = []
    with Path(path).open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    raise ValueError("строка JSONL должна содержать объект")
                rows.append(training_row_from_payload(payload))
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"Некорректная строка TrainingDataRow {line_number}: {exc}"
                ) from exc
    return tuple(rows)


def normalized_source_row_from_dict(payload: dict[str, Any]) -> NormalizedSourceRow:
    try:
        source = training_row_from_payload(payload["source_row"])
        key = NormalizedBusinessKey(**payload["business_key"])
        return NormalizedSourceRow(
            source_row=source,
            business_key=key,
            line_id=str(payload["line_id"]),
            object_code=payload.get("object_code"),
            subobject_code=payload.get("subobject_code"),
            position_code=payload.get("position_code"),
            cost_type_code=payload.get("cost_type_code"),
            drawing_code=payload.get("drawing_code"),
            basis_code=payload.get("basis_code"),
            work_name=payload.get("work_name"),
            unit=payload.get("unit"),
            work_name_tokens=tuple(payload.get("work_name_tokens", ())),
            code_tokens=tuple(payload.get("code_tokens", ())),
            unit_tokens=tuple(payload.get("unit_tokens", ())),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Некорректная normalized source row: {exc}") from exc


def load_normalized_rows_jsonl(path: Path) -> tuple[NormalizedSourceRow, ...]:
    rows: list[NormalizedSourceRow] = []
    with Path(path).open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    raise ValueError("строка JSONL должна содержать объект")
                rows.append(normalized_source_row_from_dict(payload))
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                raise ValueError(f"Некорректная строка JSONL {line_number}: {exc}") from exc
    return tuple(rows)
