"""Frozen public API contract for ExcelWriterEngine-15.0."""

from dataclasses import fields
from typing import get_type_hints

from report_processor.excel_writer import (
    EXCEL_WRITER_CONTRACT_VERSION,
    EXCEL_WRITER_ENGINE_VERSION,
    ExcelWriterAtomicError,
    ExcelWriterError,
    ExcelWriterInputError,
    ExcelWriterIntegrityError,
    ExcelWriterSafetyError,
    WriteResult,
    WriteStatus,
    WrittenCell,
    write_target_report,
)

from report_processor.quality_control import WriteDecision
from report_processor.schema import LogicalColumn


def test_public_versions_exports_enums_and_result_shapes_are_frozen() -> None:
    assert EXCEL_WRITER_CONTRACT_VERSION == "ExcelWriterContract-15.0"
    assert EXCEL_WRITER_ENGINE_VERSION == "ExcelWriterEngine-15.0"
    assert tuple(item.value for item in WriteStatus) == ("written", "skipped_decision")
    assert callable(write_target_report)
    assert issubclass(ExcelWriterInputError, ExcelWriterError)
    assert issubclass(ExcelWriterSafetyError, ExcelWriterError)
    assert issubclass(ExcelWriterIntegrityError, ExcelWriterError)
    assert issubclass(ExcelWriterAtomicError, ExcelWriterError)
    assert issubclass(ExcelWriterError, ValueError)
    assert tuple(item.name for item in fields(WrittenCell)) == (
        "calculation_id",
        "target_row_id",
        "sheet_name",
        "row_number",
        "coordinate",
        "logical_column",
        "decimal_text",
    )
    assert tuple(item.name for item in fields(WriteResult)) == (
        "write_id",
        "status",
        "decision",
        "source_file_id",
        "source_sha256",
        "output_path",
        "output_sha256",
        "written_cells",
        "calculation_ids",
        "warnings",
        "contract_version",
    )
    assert fields(WriteResult)[-1].init is False


def test_frozen_boundary_types_remain_exact() -> None:
    written_hints = get_type_hints(WrittenCell)
    result_hints = get_type_hints(WriteResult)
    assert written_hints["logical_column"] is LogicalColumn
    assert result_hints["status"] is WriteStatus
    assert result_hints["decision"] is WriteDecision
    assert result_hints["output_path"] == str | None
    assert result_hints["contract_version"] is str
