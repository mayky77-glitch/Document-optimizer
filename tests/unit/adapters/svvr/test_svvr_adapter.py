from __future__ import annotations

from decimal import Decimal

from report_processor.extraction import extract_worksheet_rows
from report_processor.schema import LogicalColumn, SheetType


def test_svvr_preserves_codes_and_text_numbers(workbook_session_factory, schema_factory):
    headers = ["Объект", "Подобъект", "Позиция", "Наименование", "Ед.", "Объём"]
    rows = [
        headers,
        ["001", "0007", "00001", "Работа А", "м", "1 234,50"],
        [None, "0008", None, "Работа Б", "шт", 0],
        ["002", "0009", "00002", "Работа В", "м3", "-2,25"],
    ]
    schema = schema_factory(
        "СВВР",
        SheetType.SVVR,
        [
            LogicalColumn.OBJECT_CODE,
            LogicalColumn.SUBOBJECT_CODE,
            LogicalColumn.POSITION_CODE,
            LogicalColumn.WORK_NAME,
            LogicalColumn.UNIT,
            LogicalColumn.CURRENT_PERIOD_QUANTITY,
        ],
        headers=headers,
    )
    with workbook_session_factory({"СВВР": rows}) as (session, _):
        result = extract_worksheet_rows(
            session,
            schema,
            document_index=None,
            document_period=None,
        )
    assert result.extracted_row_count == 3
    first = result.rows[0]
    assert first.object_code_raw == "001"
    assert first.subobject_code_raw == "0007"
    assert first.position_code_raw == "00001"
    assert first.current_period_quantity == Decimal("1234.50")
    assert result.rows[1].current_period_quantity == Decimal("0")
    assert result.rows[2].current_period_quantity == Decimal("-2.25")


def test_svvr_formula_without_cache_marks_required_value_error(
    workbook_session_factory,
    schema_factory,
):
    rows = [["Наименование", "Объём"], ["Работа", None]]
    schema = schema_factory(
        "СВВР",
        SheetType.SVVR,
        [LogicalColumn.WORK_NAME, LogicalColumn.CURRENT_PERIOD_QUANTITY],
    )
    with workbook_session_factory(
        {"СВВР": rows},
        formulas={("СВВР", "B2"): "=1+1"},
    ) as (session, _):
        result = extract_worksheet_rows(
            session,
            schema,
            document_index=None,
            document_period=None,
        )
    row = result.rows[0]
    assert row.current_period_quantity is None
    assert row.status == "ERROR"
    assert result.failed_row_count == 1
    assert any("FORMULA_WITHOUT_CACHED_VALUE" in warning for warning in row.warnings)
