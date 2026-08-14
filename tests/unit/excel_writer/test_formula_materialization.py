"""Black-box safety checks for formula materialization through the frozen writer API."""

from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook
from openpyxl.styles import Font

from fixtures.quality_control.builders import calculated_match, calculated_result
from report_processor.excel_writer import (
    ExcelWriterAtomicError,
    ExcelWriterIntegrityError,
    WriteStatus,
    ooxml,
    write_target_report,
)
from report_processor.excel_writer import formula_materialization as materializer
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _schema(path: Path) -> TargetReportSchema:
    digest = _sha256(path)
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
            TargetWorksheetSnapshot("Лист", SheetType.KS6A, "D30:E30", (), None, (), None, False),
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


def _workbook(path: Path, *, formula: bool) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Лист"
    sheet["D30"] = 5
    sheet["D30"].font = Font(bold=True)
    if formula:
        sheet["E30"] = "=D30*2"
    workbook.save(path)
    workbook.close()


def test_workbook_without_formulas_never_launches_recalculation_or_emits_formulas(
    tmp_path: Path, monkeypatch
) -> None:
    source_path = tmp_path / "source.xlsx"
    output_path = tmp_path / "output.xlsx"
    _workbook(source_path, formula=False)
    before = (source_path.stat().st_size, source_path.stat().st_mtime_ns, _sha256(source_path))

    def unexpected_process(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("LibreOffice must be skipped when the workbook has no formulas")

    monkeypatch.setattr("subprocess.run", unexpected_process)
    result = write_target_report(
        source_path, output_path, WriteDecision.ALLOW_WRITE, (_calculation(),), _schema(source_path)
    )

    assert result.status is WriteStatus.WRITTEN
    assert output_path.exists()
    assert result.output_sha256 == _sha256(output_path)
    assert (
        source_path.stat().st_size,
        source_path.stat().st_mtime_ns,
        _sha256(source_path),
    ) == before


def test_skip_decision_never_launches_recalculation_or_creates_output(
    tmp_path: Path, monkeypatch
) -> None:
    source_path = tmp_path / "source.xlsx"
    output_path = tmp_path / "output.xlsx"
    _workbook(source_path, formula=True)

    def unexpected_process(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("skipped decisions must not launch LibreOffice")

    monkeypatch.setattr("subprocess.run", unexpected_process)
    result = write_target_report(
        source_path,
        output_path,
        WriteDecision.REQUIRE_MANUAL_REVIEW,
        (_calculation(),),
        _schema(source_path),
    )

    assert result.status is WriteStatus.SKIPPED_DECISION
    assert result.output_path is None
    assert not output_path.exists()


def test_missing_libreoffice_aborts_without_changing_the_private_copy(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "formula.xlsx"
    _workbook(path, formula=True)
    before = _sha256(path)
    monkeypatch.setattr(materializer.shutil, "which", lambda _name: None)

    with pytest.raises(ExcelWriterAtomicError, match="FORMULA_RECALCULATION_UNAVAILABLE"):
        materializer.recalculate_and_materialize(path)

    assert _sha256(path) == before


def test_recalculation_timeout_aborts_without_changing_the_private_copy(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "formula.xlsx"
    _workbook(path, formula=True)
    before = _sha256(path)
    monkeypatch.setattr(materializer.shutil, "which", lambda _name: "/usr/bin/soffice")

    def timeout(*_args: object, **_kwargs: object) -> object:
        raise subprocess.TimeoutExpired("soffice", 60)

    monkeypatch.setattr(materializer.subprocess, "run", timeout)
    with pytest.raises(ExcelWriterAtomicError, match="FORMULA_RECALCULATION_FAILED"):
        materializer.recalculate_and_materialize(path)

    assert _sha256(path) == before


def test_descriptor_copy_starts_at_zero_even_after_another_reader_advanced_it(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.xlsx"
    destination = tmp_path / "input.xlsx"
    payload = b"an admitted descriptor must be copied from byte zero"
    source.write_bytes(payload)
    descriptor = os.open(source, os.O_RDONLY)
    try:
        assert os.read(descriptor, 9) == payload[:9]
        materializer._copy_descriptor(descriptor, destination)
    finally:
        os.close(descriptor)

    assert destination.read_bytes() == payload


def test_formula_package_resource_error_is_remapped_to_recalculation_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "formula.xlsx"
    _workbook(path, formula=True)

    def reject_resource(*_args: object, **_kwargs: object) -> object:
        raise ExcelWriterIntegrityError("INVALID_XLSX_PACKAGE", "injected")

    monkeypatch.setattr(materializer, "worksheet_part_map", reject_resource)
    with pytest.raises(ExcelWriterAtomicError, match="FORMULA_RECALCULATION_FAILED"):
        materializer.recalculate_and_materialize(path)


def test_failed_post_replace_formula_verification_removes_owned_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "formula.xlsx"
    _workbook(path, formula=False)
    parts = ooxml.worksheet_part_map(path)

    def fail_verification(*_args: object, **_kwargs: object) -> None:
        raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", "injected")

    monkeypatch.setattr(ooxml, "verify_materialized_package", fail_verification)
    with pytest.raises(ExcelWriterIntegrityError, match="FORMULA_MATERIALIZATION_FAILED"):
        ooxml.materialize_formula_package(path, parts, {})

    assert not path.exists()
    assert not tuple(tmp_path.glob(".excel-writer-materializing-*.xlsx"))


def test_failed_post_replace_formula_verification_preserves_a_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "formula.xlsx"
    replacement = tmp_path / "replacement.xlsx"
    _workbook(path, formula=False)
    replacement.write_bytes(b"replacement")
    parts = ooxml.worksheet_part_map(path)

    def replace_then_fail(*_args: object, **_kwargs: object) -> None:
        replacement.replace(path)
        raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", "injected")

    monkeypatch.setattr(ooxml, "verify_materialized_package", replace_then_fail)
    with pytest.raises(ExcelWriterIntegrityError, match="FORMULA_MATERIALIZATION_FAILED"):
        ooxml.materialize_formula_package(path, parts, {})

    assert path.read_bytes() == b"replacement"
