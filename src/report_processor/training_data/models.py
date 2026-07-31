from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from report_processor.hierarchy.models import HierarchyIssue


class FormulaErrorCode(StrEnum):
    NONE = "NONE"
    FORMULA_WITHOUT_CACHE = "FORMULA_WITHOUT_CACHE"
    EXCEL_ERROR = "EXCEL_ERROR"
    VALUE_READ_FAILED = "VALUE_READ_FAILED"


class DataQualityStatus(StrEnum):
    OK = "OK"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class TrainingDataRow:
    document_type: str
    document_period: str | None
    source_file_id: str
    source_filename: str
    source_sheet: str
    source_row: int
    source_row_id: str
    object_code: str | None
    subobject_code: str | None
    position_code: str | None
    cost_type_code: str | None
    drawing_code: str | None
    basis_code: str | None
    work_name_raw: str | None
    work_name_normalized: str | None
    unit_raw: str | None
    unit_normalized: str | None
    contract_quantity: Decimal | None
    period_quantity: Decimal | None
    cumulative_quantity: Decimal | None
    remaining_quantity: Decimal | None
    unit_price: Decimal | None
    contract_cost: Decimal | None
    period_cost: Decimal | None
    cumulative_cost: Decimal | None
    total_cost: Decimal | None
    is_detail: bool
    is_total: bool
    is_outdated: bool
    formula_error: FormulaErrorCode
    data_quality_status: DataQualityStatus
    line_id: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TrainingDataStatistics:
    input_rows: int
    output_rows: int
    skipped_non_detail_rows: int
    skipped_outdated_rows: int
    skipped_formula_error_rows: int
    exact_duplicates_removed: int
    line_id_collisions: int


@dataclass(frozen=True, slots=True)
class TrainingDataResult:
    rows: tuple[TrainingDataRow, ...]
    statistics: TrainingDataStatistics
    warnings: tuple[str, ...] = ()
    hierarchy_issues: tuple[HierarchyIssue, ...] = ()
