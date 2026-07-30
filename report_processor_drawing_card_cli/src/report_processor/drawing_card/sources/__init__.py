"""Source discovery and extraction public API."""

from .extractor import extract_rows
from .inspection import SourceInspection, inspect_source, select_inspections
from .manifest import build_manifest, expand_input_globs
from .readers import materialize_entry, open_reader
from .schema import detect_sheet_schema, detect_workbook_schemas

__all__ = [
    "SourceInspection",
    "build_manifest",
    "detect_sheet_schema",
    "detect_workbook_schemas",
    "expand_input_globs",
    "extract_rows",
    "inspect_source",
    "materialize_entry",
    "open_reader",
    "select_inspections",
]
