"""Publication cleanup ownership regression tests."""

from __future__ import annotations

import hashlib
import os
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook
from openpyxl.styles import Font

from fixtures.quality_control.builders import calculated_match, calculated_result
from report_processor.excel_writer import ExcelWriterIntegrityError, write_target_report
from report_processor.quality_control import WriteDecision
from report_processor.schema import LogicalColumn, SheetType
from report_processor.target_report.models import (
    TargetCellSnapshot,
    TargetColumnBinding,
    TargetPeriodIdentity,
    TargetReportSchema,
    TargetSourceFingerprint,
    TargetWorksheetSnapshot,
)


def _schema(path: Path) -> TargetReportSchema:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    source_file_id = f"synthetic:{digest}"
    return TargetReportSchema(
        version="TargetReport-9.0",
        source_fingerprint=TargetSourceFingerprint(
            "sha256", digest, path.stat().st_size, source_file_id
        ),
        period_identity=TargetPeriodIdentity(status="OK"),
        column_bindings=(
            TargetColumnBinding(LogicalColumn.CURRENT_PERIOD_QUANTITY, 4, "D", "quantity", "test"),
        ),
        worksheets=(
            TargetWorksheetSnapshot("Лист", SheetType.KS6A, "D30", (), None, (), None, False),
        ),
        object_blocks=(),
        status="OK",
        source_file_id=source_file_id,
        filename=path.name,
        source_sha256=digest,
    )


def _calculation() -> object:
    cell = TargetCellSnapshot("D30", 5, "5", Decimal("5"), 1, "0.00", None, None, "OK")
    match = calculated_match()
    target = replace(
        match.target_row,
        sheet_name="Лист",
        row_number=30,
        cells=((LogicalColumn.CURRENT_PERIOD_QUANTITY, cell),),
    )
    calculated = calculated_result(replace(match, target_row=target))
    return replace(calculated, target_row=target, quantity=Decimal("0"), cost=None)


def _workbook(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Лист"
    sheet["D30"] = 5
    sheet["D30"].font = Font(bold=True)
    workbook.save(path)
    workbook.close()


def test_reopen_failure_never_removes_concurrently_replaced_output(tmp_path, monkeypatch) -> None:
    source = tmp_path / "source.xlsx"
    output = tmp_path / "result.xlsx"
    replacement = tmp_path / "replacement.xlsx"
    _workbook(source)
    replacement.write_bytes(b"concurrent replacement")

    def replace_then_fail(path: Path) -> None:
        os.replace(replacement, path)
        raise ExcelWriterIntegrityError("REOPEN_FAILED", "injected")

    monkeypatch.setattr(
        "report_processor.excel_writer.engine._reopen_published_output", replace_then_fail
    )

    with pytest.raises(ExcelWriterIntegrityError, match="REOPEN_FAILED"):
        write_target_report(
            source, output, WriteDecision.ALLOW_WRITE, (_calculation(),), _schema(source)
        )

    assert output.read_bytes() == b"concurrent replacement"
