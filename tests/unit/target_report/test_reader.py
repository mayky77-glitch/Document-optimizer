"""Unit tests for semantic recovery and lossless target-report reading."""

from __future__ import annotations

from hashlib import sha256

from report_processor.target_report import TargetReportReadRequest, read_target_report

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
