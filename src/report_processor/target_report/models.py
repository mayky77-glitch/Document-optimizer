"""Immutable public contract for reading a target workbook (TargetReport-9.0)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from report_processor.schema import LogicalColumn, SheetType


@dataclass(frozen=True, slots=True)
class TargetDiagnostic:
    code: str
    severity: str
    message: str
    sheet_name: str | None = None
    coordinate: str | None = None


@dataclass(frozen=True, slots=True)
class TargetSourceFingerprint:
    """Identity of exactly the bytes inspected by the reader."""

    algorithm: str
    digest: str
    size_bytes: int
    source_file_id: str

    @property
    def value(self) -> str:
        return f"{self.algorithm}:{self.digest}"


@dataclass(frozen=True, slots=True)
class TargetPeriodIdentity:
    """A period pair as displayed by the target report, without inference."""

    current_period: str | None = None
    cumulative_period: str | None = None
    current_period_coordinate: str | None = None
    cumulative_period_coordinate: str | None = None
    status: str = "PERIOD_UNRESOLVED"
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TargetColumnBinding:
    logical_column: LogicalColumn
    column_index: int
    column_letter: str
    header_text: str | None
    source: str


@dataclass(frozen=True, slots=True)
class TargetReportOverride:
    """Explicit choices allowed only for the exact source fingerprint."""

    source_fingerprint: str
    sheet_name: str | None = None
    period_identity: TargetPeriodIdentity | None = None
    column_bindings: tuple[TargetColumnBinding, ...] = ()


@dataclass(frozen=True, slots=True)
class TargetReportReadRequest:
    """Read-only selection. Ambiguous selections are returned as diagnostics."""

    sheet_names: tuple[str, ...] | None = None
    override: TargetReportOverride | None = None
    include_empty_rows: bool = False


@dataclass(frozen=True, slots=True)
class TargetFormulaSnapshot:
    formula: str | None
    cached_value: object
    formula_data_type: str | None
    cached_data_type: str | None
    cache_state: str
    raw_formula_lexeme: str | None = None
    raw_cached_lexeme: str | None = None


@dataclass(frozen=True, slots=True)
class TargetCellSnapshot:
    coordinate: str
    raw_value: object
    raw_lexeme: str | None
    numeric_value: Decimal | None
    style_id: int | None
    number_format: str | None
    comment_text: str | None
    formula: TargetFormulaSnapshot | None
    status: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TargetWorksheetSnapshot:
    sheet_name: str
    sheet_type: SheetType
    dimensions: str | None
    merged_ranges: tuple[str, ...]
    auto_filter_ref: str | None
    comments: tuple[tuple[str, str], ...]
    freeze_panes: str | None
    hidden: bool


@dataclass(frozen=True, slots=True)
class TargetObjectBlock:
    sheet_name: str
    start_row: int
    end_row: int
    object_code: str | None
    object_name: str | None


@dataclass(frozen=True, slots=True)
class TargetReportRow:
    """Canonical immutable row. Numeric values originate from OOXML lexemes."""

    schema_version: str
    sheet_name: str
    sheet_type: SheetType
    row_number: int
    object_code: str | None
    object_name: str | None
    position_code: str | None
    work_name: str | None
    cells: tuple[tuple[LogicalColumn, TargetCellSnapshot], ...]
    status: str
    warnings: tuple[str, ...] = ()

    def cell_for(self, logical_column: LogicalColumn) -> TargetCellSnapshot | None:
        return next((cell for key, cell in self.cells if key == logical_column), None)


@dataclass(frozen=True, slots=True)
class WritableCellPlan:
    """Future-write metadata only; this package never applies it."""

    version: str
    sheet_name: str
    coordinate: str
    expected_source_fingerprint: str
    expected_raw_lexeme: str | None
    status: str = "READ_ONLY_PLAN"


@dataclass(frozen=True, slots=True)
class StructuralMutationPlan:
    version: str
    expected_source_fingerprint: str
    operations: tuple[str, ...] = ()
    status: str = "READ_ONLY_PLAN"


@dataclass(frozen=True, slots=True)
class PackageSanitizationPlan:
    version: str
    expected_source_fingerprint: str
    package_entries: tuple[str, ...] = ()
    status: str = "READ_ONLY_PLAN"


@dataclass(frozen=True, slots=True)
class TargetReportSchema:
    version: str
    source_fingerprint: TargetSourceFingerprint
    period_identity: TargetPeriodIdentity
    column_bindings: tuple[TargetColumnBinding, ...]
    worksheets: tuple[TargetWorksheetSnapshot, ...]
    object_blocks: tuple[TargetObjectBlock, ...]
    status: str
    diagnostics: tuple[TargetDiagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class TargetReportResult:
    schema: TargetReportSchema
    rows: tuple[TargetReportRow, ...]
    writable_cell_plans: tuple[WritableCellPlan, ...]
    structural_mutation_plan: StructuralMutationPlan
    package_sanitization_plan: PackageSanitizationPlan
    status: str
    diagnostics: tuple[TargetDiagnostic, ...] = ()
