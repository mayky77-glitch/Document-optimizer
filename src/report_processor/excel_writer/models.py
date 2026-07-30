"""Frozen public data contract for ExcelWriter-15.1."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from report_processor.quality_control import WriteDecision
from report_processor.schema import LogicalColumn

EXCEL_WRITER_CONTRACT_VERSION = "ExcelWriterContract-15.1"
EXCEL_WRITER_ENGINE_VERSION = "ExcelWriterEngine-15.1"


class WriteStatus(StrEnum):
    WRITTEN = "written"
    SKIPPED_DECISION = "skipped_decision"


@dataclass(frozen=True, slots=True)
class WrittenCell:
    calculation_id: str
    target_row_id: str
    sheet_name: str
    row_number: int
    coordinate: str
    logical_column: LogicalColumn
    decimal_text: str


@dataclass(frozen=True, slots=True)
class WriteResult:
    write_id: str
    status: WriteStatus
    decision: WriteDecision
    source_file_id: str
    source_sha256: str
    output_path: str | None
    output_sha256: str | None
    written_cells: tuple[WrittenCell, ...]
    calculation_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    contract_version: str = field(init=False, default=EXCEL_WRITER_CONTRACT_VERSION)
