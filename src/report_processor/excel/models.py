from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from report_processor.materialization.models import MaterializedSource


@dataclass(frozen=True, slots=True)
class ExcelFormatResult:
    extension: str
    format_name: str
    supported: bool
    macro_enabled: bool
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class WorkbookOpenRequest:
    source: MaterializedSource
    read_only: bool = True
    keep_links: bool = True


@dataclass(frozen=True, slots=True)
class WorkbookMetadata:
    filename: str
    extension: str
    size_bytes: int
    macro_enabled: bool
    sheet_count: int
    sheet_names: tuple[str, ...]
    has_hidden_sheets: bool
    has_very_hidden_sheets: bool
    warnings: tuple[str, ...] = ()
    defined_names_count: int | None = None
    external_links_count: int | None = None


@dataclass(frozen=True, slots=True)
class WorksheetMetadata:
    title: str
    index: int
    state: str
    max_row_reported: int
    max_column_reported: int
    dimensions_reported: str | None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CellReference:
    sheet_name: str
    coordinate: str


@dataclass(frozen=True, slots=True)
class CellSnapshot:
    sheet_name: str
    coordinate: str
    formula_value: object
    cached_value: object
    formula_data_type: str | None
    cached_data_type: str | None
    is_formula: bool
    has_cached_value: bool
    formula_error: str | None
    cached_error: str | None
    status: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class WorkbookPreparationResult:
    status: str
    source: MaterializedSource | None
    workbook_metadata: WorkbookMetadata | None
    worksheet_metadata: tuple[WorksheetMetadata, ...]
    warnings: tuple[str, ...] = ()


@dataclass(slots=True)
class DualWorkbookSession:
    formula_workbook: Any
    value_workbook: Any
    source: MaterializedSource
    format_result: ExcelFormatResult
    keep_vba: bool
    metadata: WorkbookMetadata | None = None
    structure_cache: dict[str, object] = field(default_factory=dict)
    closed: bool = False
    formula_source_path: Path = field(init=False)
    value_source_path: Path = field(init=False)

    def __post_init__(self) -> None:
        self.formula_source_path = self.source.local_path
        self.value_source_path = self.source.local_path

    @property
    def sheet_names(self) -> tuple[str, ...]:
        """Return the validated shared sheet order for both read-only views."""

        return tuple(self.formula_workbook.sheetnames)

    @staticmethod
    def _close_workbook(workbook: Any) -> None:
        try:
            workbook.close()
        finally:
            vba_archive = getattr(workbook, "vba_archive", None)
            if vba_archive is not None and getattr(vba_archive, "fp", None) is not None:
                vba_archive.close()

    def close(self) -> None:
        if self.closed:
            return
        try:
            self._close_workbook(self.formula_workbook)
        finally:
            try:
                self._close_workbook(self.value_workbook)
            finally:
                self.closed = True
