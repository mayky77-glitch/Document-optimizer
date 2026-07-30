from __future__ import annotations

from importlib import import_module
from typing import Any

from .cell_values import extract_cell_value
from .config import ExtractionConfig
from .exceptions import (
    AdapterNotAvailableError,
    ExtractionError,
    ExtractionSchemaError,
    ExtractionSerializationError,
    RowReadError,
)
from .extraction_plan import build_extraction_plan
from .models import (
    AdapterSchemaValidation,
    CanonicalSourceRow,
    ExtractedCellValue,
    ExtractionPlan,
    ExtractionResult,
    JsonlWriteResult,
    ParsedNumericValue,
    ParsedTextValue,
    RowValidationIssue,
    SourceLocation,
    ValueProvenance,
)
from .numeric_values import parse_decimal_value
from .provenance import make_row_id
from .row_boundaries import is_effectively_empty_row, looks_like_repeated_header
from .row_iterator import iter_source_row_numbers
from .row_validation import validate_canonical_source_row
from .schema_loader import load_workbook_schema_json
from .serialization import (
    build_extraction_metadata,
    save_extraction_result_json,
    save_extraction_results_json,
    save_extraction_results_jsonl,
    save_rows_jsonl,
)
from .text_values import parse_text_value

_LAZY_EXTRACTOR_EXPORTS = {
    "create_workbook_extraction_stream",
    "extract_supported_workbook_rows",
    "extract_worksheet_rows",
    "iter_worksheet_rows",
}


def __getattr__(name: str) -> Any:
    """Load adapter-dependent orchestration lazily to avoid import cycles."""
    if name not in _LAZY_EXTRACTOR_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(".extractor", __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value


__all__ = [
    "AdapterNotAvailableError",
    "AdapterSchemaValidation",
    "CanonicalSourceRow",
    "ExtractedCellValue",
    "ExtractionConfig",
    "ExtractionError",
    "ExtractionPlan",
    "ExtractionResult",
    "ExtractionSchemaError",
    "ExtractionSerializationError",
    "JsonlWriteResult",
    "ParsedNumericValue",
    "ParsedTextValue",
    "RowReadError",
    "RowValidationIssue",
    "SourceLocation",
    "ValueProvenance",
    "build_extraction_metadata",
    "build_extraction_plan",
    "create_workbook_extraction_stream",
    "extract_cell_value",
    "extract_supported_workbook_rows",
    "extract_worksheet_rows",
    "is_effectively_empty_row",
    "iter_source_row_numbers",
    "iter_worksheet_rows",
    "load_workbook_schema_json",
    "looks_like_repeated_header",
    "make_row_id",
    "parse_decimal_value",
    "parse_text_value",
    "save_extraction_result_json",
    "save_extraction_results_json",
    "save_extraction_results_jsonl",
    "save_rows_jsonl",
    "validate_canonical_source_row",
]
