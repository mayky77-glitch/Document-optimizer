from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from report_processor.schema import ColumnResolution, LogicalColumn, SheetType


@dataclass(frozen=True, slots=True)
class SourceLocation:
    source_file_id: str
    filename: str
    sheet_name: str
    sheet_type: str
    row_number: int
    column_number: int | None = None
    column_letter: str | None = None
    coordinate: str | None = None


@dataclass(frozen=True, slots=True)
class ValueProvenance:
    location: SourceLocation
    logical_column: str
    header_text: str | None
    formula: str | None
    cached_value_available: bool
    value_source: str
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExtractedCellValue:
    logical_column: str
    coordinate: str
    raw_formula_value: object
    raw_cached_value: object
    effective_value: object
    effective_value_source: str
    formula_data_type: str | None
    cached_data_type: str | None
    is_formula: bool
    is_empty: bool
    is_error: bool
    status: str
    warnings: tuple[str, ...]
    provenance: ValueProvenance


@dataclass(frozen=True, slots=True)
class ParsedNumericValue:
    raw_value: object
    value: Decimal | None
    status: str
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ParsedTextValue:
    raw_value: object
    value: str | None
    status: str
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CanonicalSourceRow:
    row_id: str
    source_type: str
    source_location: SourceLocation
    document_index: str | None
    document_period: str | None
    object_code_raw: str | None
    object_name_raw: str | None
    subobject_code_raw: str | None
    subobject_name_raw: str | None
    position_code_raw: str | None
    work_name_raw: str | None
    unit_raw: str | None
    contract_quantity: Decimal | None
    current_period_quantity: Decimal | None
    cumulative_quantity: Decimal | None
    remaining_quantity: Decimal | None
    unit_price: Decimal | None
    contract_cost: Decimal | None
    current_period_cost: Decimal | None
    cumulative_cost: Decimal | None
    total_cost: Decimal | None
    basis_code_raw: str | None
    drawing_code_raw: str | None
    cost_type_code_raw: str | None
    source_values: tuple[ExtractedCellValue, ...]
    status: str
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExtractionPlan:
    sheet_name: str
    sheet_type: SheetType
    data_start_row: int
    max_end_row: int
    columns: tuple[ColumnResolution, ...]
    required_columns: tuple[LogicalColumn, ...]
    optional_columns: tuple[LogicalColumn, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AdapterSchemaValidation:
    valid: bool
    missing_required_columns: tuple[LogicalColumn, ...]
    missing_optional_columns: tuple[LogicalColumn, ...]
    status: str
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    source_file_id: str
    filename: str
    sheet_name: str
    sheet_type: SheetType
    rows: tuple[CanonicalSourceRow, ...]
    scanned_row_count: int
    extracted_row_count: int
    skipped_empty_row_count: int
    skipped_header_row_count: int
    failed_row_count: int
    start_row: int
    last_scanned_row: int | None
    stop_reason: str
    status: str
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RowValidationIssue:
    code: str
    severity: str
    message: str
    coordinates: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class JsonlWriteResult:
    output_path: Path
    meta_path: Path
    row_count: int
    bytes_written: int
