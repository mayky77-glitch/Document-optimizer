"""Unit tests for semantic recovery and lossless target-report reading."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from report_processor.target_report import TargetReportReadRequest, read_target_report

from report_processor.excel import WorkbookOpenRequest, open_dual_workbook
from report_processor.materialization.models import MaterializedSource
from report_processor.schema import LogicalColumn, SheetType, WorkbookSchema


def _schema(schema_factory, worksheet) -> WorkbookSchema:
    return WorkbookSchema(
        "file-001",
        "source.xlsx",
        (worksheet,),
        {worksheet.sheet_type.value: (worksheet.sheet_name,)},
        {worksheet.sheet_type.value: worksheet.sheet_name},
        1.0,
        "OK",
    )


def _open_synthetic_session(path: Path):
    source = MaterializedSource(
        local_path=path,
        original_file_id="target-fixture-001",
        original_relative_path=path.name,
        source_kind="file",
        archive_path=None,
        was_extracted=False,
        temporary=False,
        size_bytes=path.stat().st_size,
        extension=".xlsx",
        cleanup_required=False,
    )
    return open_dual_workbook(WorkbookOpenRequest(source))


def test_reader_preserves_leading_zeroes_decimal_lexemes_and_formula_state(
    workbook_session_factory, schema_factory
) -> None:
    columns = (
        LogicalColumn.OBJECT_CODE,
        LogicalColumn.POSITION_CODE,
        LogicalColumn.WORK_NAME,
        LogicalColumn.CURRENT_PERIOD_QUANTITY,
        LogicalColumn.CUMULATIVE_QUANTITY,
    )
    with workbook_session_factory(
        {
            "Целевой": [
                ["object", "position", "work", "current", "cumulative"],
                ["0007", "000042", "Монтаж", "001.250", "=D2"],
            ]
        },
        formulas={("Целевой", "E2"): "=D2"},
    ) as (session, _):
        worksheet = schema_factory(
            "Целевой", SheetType.KS6A, columns, headers=["", "", "", "Июль", "Итого"]
        )
        result = read_target_report(
            session, _schema(schema_factory, worksheet), TargetReportReadRequest()
        )

    assert result.status == "OK"
    assert result.schema.version == "TargetReportSchema-9.0"
    assert result.schema.period_identity.status == "OK"
    row = result.rows[0]
    assert row.schema_version == "TargetReportRow-9.0"
    assert row.object_code == "0007"
    assert row.position_code == "000042"
    current = row.cell_for(LogicalColumn.CURRENT_PERIOD_QUANTITY)
    cumulative = row.cell_for(LogicalColumn.CUMULATIVE_QUANTITY)
    assert current.raw_lexeme == "001.250"
    assert str(current.numeric_value) == "1.250"
    assert cumulative.formula.formula == "=D2"
    assert cumulative.formula.cache_state == "FORMULA_WITHOUT_CACHED_VALUE"


def test_generic_unknown_sheet_is_semantically_recovered_when_shape_is_unambiguous(
    workbook_session_factory, schema_factory
) -> None:
    columns = (
        LogicalColumn.OBJECT_CODE,
        LogicalColumn.WORK_NAME,
        LogicalColumn.CURRENT_PERIOD_QUANTITY,
        LogicalColumn.CUMULATIVE_QUANTITY,
    )
    with workbook_session_factory(
        {
            "Похоже на отчёт": [
                ["Код", "Работа", "Текущий", "Накопительный"],
                ["0007", "Монтаж", 1, 2],
            ]
        }
    ) as (session, _):
        worksheet = schema_factory("Похоже на отчёт", SheetType.UNKNOWN, columns)
        result = read_target_report(
            session, _schema(schema_factory, worksheet), TargetReportReadRequest()
        )

    assert result.status == "OK"
    assert result.rows[0].object_code == "0007"
    assert result.schema.period_identity.status == "OK"


def test_reader_retains_structural_metadata_and_source_bytes(
    workbook_session_factory, schema_factory
) -> None:
    with workbook_session_factory({"Целевой": [["Код", "Работа"], ["0007", "Монтаж"]]}) as (
        session,
        path,
    ):
        before = path.read_bytes()
        worksheet = schema_factory(
            "Целевой", SheetType.KS6A, (LogicalColumn.OBJECT_CODE, LogicalColumn.WORK_NAME)
        )
        result = read_target_report(
            session, _schema(schema_factory, worksheet), TargetReportReadRequest()
        )
        after = path.read_bytes()

    assert before == after
    assert result.schema.source_fingerprint.digest == sha256(before).hexdigest()
    assert result.schema.source_fingerprint.size_bytes == len(before)
    assert (
        result.writable_cell_plans[0].expected_source_fingerprint
        == result.schema.source_fingerprint.value
    )


def test_reader_preserves_merged_filter_style_comment_and_dimensions(
    tmp_path: Path, schema_factory
) -> None:
    path = tmp_path / "synthetic-target.xlsx"
    book = Workbook()
    sheet = book.active
    sheet.title = "Целевой"
    sheet.merge_cells("A1:B1")
    sheet["A1"] = "Объект"
    sheet["A2"] = "0007"
    sheet["B2"] = "Монтаж"
    sheet["B2"].number_format = "@"
    sheet["B2"].comment = Comment("synthetic note", "test")
    sheet.auto_filter.ref = "A1:B2"
    sheet.freeze_panes = "A2"
    book.save(path)
    book.close()

    with _open_synthetic_session(path) as session:
        worksheet = schema_factory(
            "Целевой", SheetType.KS6A, (LogicalColumn.OBJECT_CODE, LogicalColumn.WORK_NAME)
        )
        result = read_target_report(
            session, _schema(schema_factory, worksheet), TargetReportReadRequest()
        )

    snapshot = result.schema.worksheets[0]
    work_name = result.rows[0].cell_for(LogicalColumn.WORK_NAME)
    assert snapshot.dimensions == "A1:B2"
    assert snapshot.merged_ranges == ("A1:B1",)
    assert snapshot.auto_filter_ref == "A1:B2"
    assert snapshot.freeze_panes == "A2"
    assert snapshot.comments == (("B2", "synthetic note"),)
    assert work_name.number_format == "@"
    assert work_name.comment_text == "synthetic note"
