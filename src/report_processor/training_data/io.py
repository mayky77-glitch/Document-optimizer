from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from report_processor.extraction.models import CanonicalSourceRow
from report_processor.storage import DuckDBStore
from report_processor.storage.exceptions import StorageSchemaError
from report_processor.storage.serialization import (
    canonical_row_from_payload,
    deterministic_json,
)

InputFormat = Literal["auto", "duckdb", "jsonl"]


def canonical_source_row_from_dict(data: dict[str, Any]) -> CanonicalSourceRow:
    try:
        return canonical_row_from_payload(deterministic_json(data))
    except StorageSchemaError as exc:
        raise ValueError(str(exc)) from exc


def load_canonical_rows_jsonl(path: Path) -> tuple[CanonicalSourceRow, ...]:
    rows: list[CanonicalSourceRow] = []
    with Path(path).open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    raise ValueError("строка JSONL должна содержать объект")
                rows.append(canonical_source_row_from_dict(payload))
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                raise ValueError(f"Некорректная строка JSONL {line_number}: {exc}") from exc
    return tuple(rows)


def load_canonical_rows_duckdb(path: Path) -> tuple[CanonicalSourceRow, ...]:
    database_path = Path(path)
    if not database_path.is_file():
        raise FileNotFoundError(database_path)
    with DuckDBStore(database_path, create_parent=False, read_only=True) as store:
        return tuple(store.iter_all_rows())


def resolve_input_format(
    path: Path, input_format: InputFormat = "auto"
) -> Literal["duckdb", "jsonl"]:
    if input_format == "duckdb" or input_format == "jsonl":
        return input_format
    if input_format != "auto":
        raise ValueError(f"Неподдерживаемый формат входа: {input_format}")
    suffix = Path(path).suffix.casefold()
    if suffix == ".duckdb":
        return "duckdb"
    if suffix == ".jsonl":
        return "jsonl"
    raise ValueError(
        "Не удалось определить формат входа: используйте расширение .duckdb/.jsonl "
        "или --input-format"
    )


def load_canonical_rows(
    path: Path,
    *,
    input_format: InputFormat = "auto",
) -> tuple[CanonicalSourceRow, ...]:
    resolved = resolve_input_format(path, input_format)
    if resolved == "duckdb":
        return load_canonical_rows_duckdb(path)
    return load_canonical_rows_jsonl(path)
