"""Immutable public models produced by workbook structure detection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class SheetType(StrEnum):
    KS2 = "ks2"
    KS3 = "ks3"
    KS6A = "ks6a"
    SVVR = "svvr"
    KS2_REGISTRY = "ks2_registry"
    ADDITIONAL_REPORT = "additional_report"
    SUBOBJECT_REFERENCE = "subobject_reference"
    VISR = "visr"
    DRDC = "drdc"
    PROTOCOL = "protocol"
    TITLE = "title"
    TECHNICAL = "technical"
    UNKNOWN = "unknown"


class LogicalColumn(StrEnum):
    ROW_NUMBER = "row_number"
    DOCUMENT_INDEX = "document_index"
    STAGE = "stage"
    OBJECT_CODE = "object_code"
    OBJECT_NAME = "object_name"
    SUBOBJECT_CODE = "subobject_code"
    SUBOBJECT_NAME = "subobject_name"
    POSITION_CODE = "position_code"
    WORK_NAME = "work_name"
    UNIT = "unit"
    CONTRACT_QUANTITY = "contract_quantity"
    CURRENT_PERIOD_QUANTITY = "current_period_quantity"
    CUMULATIVE_QUANTITY = "cumulative_quantity"
    REMAINING_QUANTITY = "remaining_quantity"
    UNIT_PRICE = "unit_price"
    CURRENT_PERIOD_COST = "current_period_cost"
    CUMULATIVE_COST = "cumulative_cost"
    TOTAL_COST = "total_cost"
    LIMIT_VALUE = "limit_value"
    BASIS_CODE = "basis_code"
    DRAWING_CODE = "drawing_code"
    COST_TYPE_CODE = "cost_type_code"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SheetTypeCandidate:
    sheet_type: SheetType
    score: float
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SheetClassification:
    sheet_name: str
    sheet_type: SheetType
    confidence: float
    name_score: float
    content_score: float
    matched_name_markers: tuple[str, ...]
    matched_content_markers: tuple[str, ...]
    alternative_types: tuple[SheetTypeCandidate, ...]
    status: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ScannedCell:
    row: int
    column: int
    coordinate: str
    raw_value: Any
    normalized_text: str | None
    is_formula: bool
    is_empty: bool
    is_merged_anchor: bool
    merged_range: str | None


@dataclass(frozen=True, slots=True)
class WorksheetScanWindow:
    sheet_name: str
    max_scanned_row: int
    max_scanned_column: int
    nonempty_cell_count: int
    cells: tuple[ScannedCell, ...]
    merged_ranges: tuple[str, ...]
    stopped_early: bool
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MergedRangeInfo:
    range_string: str
    min_row: int
    max_row: int
    min_column: int
    max_column: int
    anchor_coordinate: str
    anchor_value: Any


@dataclass(frozen=True, slots=True)
class HeaderCandidate:
    start_row: int
    end_row: int
    score: float
    nonempty_columns: int
    text_cell_count: int
    numeric_cell_count: int
    matched_aliases: tuple[str, ...]
    penalties: tuple[str, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ComposedHeader:
    column_index: int
    column_letter: str
    parts: tuple[str, ...]
    raw_text: str
    normalized_text: str
    is_empty: bool
    source_coordinates: tuple[str, ...]
    merged_sources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ColumnCandidate:
    column_index: int
    column_letter: str
    header_text: str
    score: float
    matched_tokens: tuple[str, ...]
    rejected_tokens: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ColumnResolution:
    logical_column: LogicalColumn
    column_index: int | None
    column_letter: str | None
    header_text: str | None
    confidence: float
    matched_rule: str | None
    alternatives: tuple[ColumnCandidate, ...]
    status: str
    warnings: tuple[str, ...] = ()
    is_manual: bool = False


@dataclass(frozen=True, slots=True)
class SchemaValidationIssue:
    code: str
    severity: str
    message: str
    related_columns: tuple[str, ...] = ()
    related_rows: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class WorksheetSchema:
    sheet_name: str
    sheet_type: SheetType
    classification: SheetClassification
    header_start_row: int | None
    header_end_row: int | None
    data_start_row: int | None
    first_table_column: int | None
    last_table_column: int | None
    headers: tuple[ComposedHeader, ...]
    columns: tuple[ColumnResolution, ...]
    confidence: float
    status: str
    warnings: tuple[str, ...] = ()
    validation_issues: tuple[SchemaValidationIssue, ...] = ()
    manual_overrides: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class WorkbookSchema:
    source_file_id: str
    filename: str
    worksheets: tuple[WorksheetSchema, ...]
    sheets_by_type: dict[str, tuple[str, ...]]
    primary_sheets: dict[str, str | None]
    confidence: float
    status: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ColumnOverride:
    logical_column: LogicalColumn
    column: str


@dataclass(frozen=True, slots=True)
class WorksheetSchemaOverride:
    sheet_name: str
    sheet_type: SheetType | None = None
    header_start_row: int | None = None
    header_end_row: int | None = None
    data_start_row: int | None = None
    column_overrides: tuple[ColumnOverride, ...] = ()


@dataclass(frozen=True, slots=True)
class SheetTypeSignature:
    sheet_type: SheetType
    strong_markers: tuple[str, ...]
    weak_markers: tuple[str, ...]
    negative_markers: tuple[str, ...]
    min_score: float


@dataclass(frozen=True, slots=True)
class ColumnAliasRule:
    logical_column: LogicalColumn
    exact_aliases: tuple[str, ...]
    required_tokens: tuple[str, ...]
    optional_tokens: tuple[str, ...]
    forbidden_tokens: tuple[str, ...]
    applicable_sheet_types: tuple[SheetType, ...]
    priority: int


@dataclass(frozen=True, slots=True)
class SheetColumnRequirements:
    sheet_type: SheetType
    required: tuple[LogicalColumn, ...]
    optional: tuple[LogicalColumn, ...]
