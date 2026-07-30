from __future__ import annotations

from report_processor.extraction import ExtractionConfig, extract_supported_workbook_rows
from report_processor.schema import LogicalColumn, SheetType, WorkbookSchema


def test_supported_sheets_are_extracted_separately(workbook_session_factory, schema_factory):
    rows = {
        "КС-2": [["Наименование", "Количество"], ["Работа 1", 1]],
        "КС-6а": [["Наименование", "Количество"], ["Работа 2", 2]],
        "СВВР": [["Наименование", "Количество"], ["Работа 3", 3]],
        "Технический": [["x"], ["ignore"]],
    }
    schemas = (
        schema_factory(
            "КС-2",
            SheetType.KS2,
            [LogicalColumn.WORK_NAME, LogicalColumn.CURRENT_PERIOD_QUANTITY],
        ),
        schema_factory(
            "КС-6а",
            SheetType.KS6A,
            [LogicalColumn.WORK_NAME, LogicalColumn.CURRENT_PERIOD_QUANTITY],
        ),
        schema_factory(
            "СВВР",
            SheetType.SVVR,
            [LogicalColumn.WORK_NAME, LogicalColumn.CURRENT_PERIOD_QUANTITY],
        ),
        schema_factory("Технический", SheetType.TECHNICAL, [LogicalColumn.WORK_NAME]),
    )
    workbook_schema = WorkbookSchema("file-001", "source.xlsx", schemas, {}, {}, 1.0, "OK")
    with workbook_session_factory(rows) as (session, _):
        results = extract_supported_workbook_rows(
            session,
            workbook_schema,
            document_index="1006 (682)",
            document_period="2026-07",
            config=ExtractionConfig(max_consecutive_empty_rows=2),
        )
    assert [result.sheet_type for result in results] == [
        SheetType.KS2,
        SheetType.KS6A,
        SheetType.SVVR,
    ]
    assert [result.rows[0].work_name_raw for result in results] == [
        "Работа 1",
        "Работа 2",
        "Работа 3",
    ]
    assert len({result.rows[0].row_id for result in results}) == 3


def test_empty_rows_are_optionally_included(workbook_session_factory, schema_factory):
    rows = {"КС-2": [["Наименование"], ["Работа"], [None]]}
    schema = schema_factory("КС-2", SheetType.KS2, [LogicalColumn.WORK_NAME])
    workbook_schema = WorkbookSchema("file-001", "source.xlsx", (schema,), {}, {}, 1.0, "OK")
    with workbook_session_factory(rows) as (session, _):
        results = extract_supported_workbook_rows(
            session,
            workbook_schema,
            document_index=None,
            document_period=None,
            config=ExtractionConfig(include_empty_rows=True, max_consecutive_empty_rows=1),
        )
    assert results[0].extracted_row_count == 2
    assert results[0].rows[-1].status == "EMPTY"
