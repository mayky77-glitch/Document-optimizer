"""Deterministic normalization of block 7 training rows (schema 8.0)."""

from .identity import make_line_id
from .io import load_normalized_rows_jsonl
from .models import (
    NormalizationConfig,
    NormalizationResult,
    NormalizationStatistics,
    NormalizedBusinessKey,
    NormalizedSourceRow,
    TypoDictionaries,
)
from .processor import normalize_training_data, normalize_training_row, normalize_training_rows
from .serialization import (
    SCHEMA_VERSION,
    build_normalization_metadata,
    save_normalized_rows_jsonl,
)

__all__ = [
    "SCHEMA_VERSION",
    "NormalizationConfig",
    "NormalizationResult",
    "NormalizationStatistics",
    "NormalizedBusinessKey",
    "NormalizedSourceRow",
    "TypoDictionaries",
    "build_normalization_metadata",
    "load_normalized_rows_jsonl",
    "make_line_id",
    "normalize_training_data",
    "normalize_training_row",
    "normalize_training_rows",
    "save_normalized_rows_jsonl",
]
