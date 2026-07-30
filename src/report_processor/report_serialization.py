from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from report_processor.excel.models import CellSnapshot, WorkbookMetadata, WorksheetMetadata
from report_processor.materialization.models import MaterializedSource


def _json_value(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


def build_inspection_report(
    *,
    source: MaterializedSource,
    workbook: WorkbookMetadata,
    worksheets: tuple[WorksheetMetadata, ...],
    cells: tuple[CellSnapshot, ...] = (),
    warnings: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "status": "OK",
        "source": {
            "file_id": source.original_file_id,
            "relative_path": source.original_relative_path,
            "source_kind": source.source_kind,
            "was_extracted": source.was_extracted,
            "size_bytes": source.size_bytes,
        },
        "workbook": _json_value(workbook),
        "worksheets": _json_value(worksheets),
        "cells": _json_value(cells),
        "warnings": list(dict.fromkeys((*source.warnings, *workbook.warnings, *warnings))),
    }


def save_inspection_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=output_path.parent, delete=False
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(report, temporary_file, ensure_ascii=False, indent=2, sort_keys=True)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, output_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
