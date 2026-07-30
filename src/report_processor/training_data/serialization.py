from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from report_processor.extraction.models import JsonlWriteResult
from report_processor.extraction.serialization import save_rows_jsonl

from .models import TrainingDataResult

SCHEMA_VERSION = "7.0"


def build_training_data_metadata(result: TrainingDataResult) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "statistics": asdict(result.statistics),
        "warnings": list(result.warnings),
    }


def save_training_data_jsonl(
    result: TrainingDataResult,
    output_path: Path,
) -> JsonlWriteResult:
    return save_rows_jsonl(
        result.rows,
        Path(output_path),
        metadata=build_training_data_metadata(result),
    )
