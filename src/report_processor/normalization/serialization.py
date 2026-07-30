from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from report_processor.extraction.models import JsonlWriteResult
from report_processor.extraction.serialization import save_rows_jsonl

from .models import NormalizationResult, NormalizedSourceRow

SCHEMA_VERSION = "8.0"


def normalized_source_row_to_payload(row: NormalizedSourceRow) -> dict[str, Any]:
    """Return a JSON-compatible payload without converting Decimal through float."""
    return asdict(row)


def build_normalization_metadata(result: NormalizationResult) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "statistics": asdict(result.statistics),
    }


def save_normalized_rows_jsonl(
    result: NormalizationResult,
    output_path: Path,
) -> JsonlWriteResult:
    return save_rows_jsonl(
        result.rows,
        Path(output_path),
        metadata=build_normalization_metadata(result),
    )
