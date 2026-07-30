from __future__ import annotations

from report_processor.extraction import (
    ExtractionConfig,
    build_extraction_plan,
    extract_cell_value,
    is_effectively_empty_row,
    iter_source_row_numbers,
    looks_like_repeated_header,
)
from report_processor.schema import LogicalColumn, SheetType


def test_zero_row_is_not_empty(workbook_session_factory, schema_factory):
    schema = schema_factory(
        "КС-2",
        SheetType.KS2,
        [LogicalColumn.WORK_NAME, LogicalColumn.CURRENT_PERIOD_QUANTITY],
    )
    with workbook_session_factory({"КС-2": [["Наименование", "Количество"], [None, 0]]}) as (
        session,
        _,
    ):
        values = tuple(
            extract_cell_value(
                session,
                sheet_name="КС-2",
                row_number=2,
                column_resolution=column,
                sheet_type=SheetType.KS2,
            )
            for column in schema.columns
        )
    assert not is_effectively_empty_row(
        values,
        key_columns=(LogicalColumn.WORK_NAME, LogicalColumn.CURRENT_PERIOD_QUANTITY),
    )


def test_single_empty_row_does_not_stop_but_limit_does(workbook_session_factory, schema_factory):
    rows = [["Наименование", "Количество"], ["A", 1], [None, None], ["B", 2]]
    rows.extend([[None, None]] * 3)
    rows.append(["C", 3])
    schema = schema_factory(
        "КС-2",
        SheetType.KS2,
        [LogicalColumn.WORK_NAME, LogicalColumn.CURRENT_PERIOD_QUANTITY],
    )
    with workbook_session_factory({"КС-2": rows}) as (session, _):
        plan = build_extraction_plan(
            session,
            schema,
            ExtractionConfig(max_rows=100, max_consecutive_empty_rows=3),
        )
        numbers = list(
            iter_source_row_numbers(
                session,
                plan,
                ExtractionConfig(max_rows=100, max_consecutive_empty_rows=3),
            )
        )
    assert numbers == [2, 3, 4, 5, 6, 7]
    assert 8 not in numbers


def test_max_rows_is_observed(workbook_session_factory, schema_factory):
    rows = [["Наименование"]] + [[f"Работа {i}"] for i in range(20)]
    schema = schema_factory("КС-2", SheetType.KS2, [LogicalColumn.WORK_NAME])
    config = ExtractionConfig(max_rows=5, max_consecutive_empty_rows=20)
    with workbook_session_factory({"КС-2": rows}) as (session, _):
        plan = build_extraction_plan(session, schema, config)
        assert list(iter_source_row_numbers(session, plan, config)) == [2, 3, 4, 5, 6]


def test_repeated_header_is_recognized(workbook_session_factory, schema_factory):
    headers = ["Наименование работ", "Количество", "Стоимость"]
    schema = schema_factory(
        "КС-2",
        SheetType.KS2,
        [
            LogicalColumn.WORK_NAME,
            LogicalColumn.CURRENT_PERIOD_QUANTITY,
            LogicalColumn.CURRENT_PERIOD_COST,
        ],
        headers=headers,
    )
    with workbook_session_factory({"КС-2": [headers, headers]}) as (session, _):
        values = tuple(
            extract_cell_value(
                session,
                sheet_name="КС-2",
                row_number=2,
                column_resolution=column,
                sheet_type=SheetType.KS2,
            )
            for column in schema.columns
        )
    assert looks_like_repeated_header(values, schema)


def test_formula_without_cache_can_be_excluded_from_content(
    workbook_session_factory,
    schema_factory,
):
    schema = schema_factory("КС-2", SheetType.KS2, [LogicalColumn.WORK_NAME])
    with workbook_session_factory(
        {"КС-2": [["Наименование"], [None]]},
        formulas={("КС-2", "A2"): "=A1"},
    ) as (session, _):
        value = extract_cell_value(
            session,
            sheet_name="КС-2",
            row_number=2,
            column_resolution=schema.columns[0],
            sheet_type=SheetType.KS2,
        )
    values = (value,)
    assert not is_effectively_empty_row(
        values,
        key_columns=(LogicalColumn.WORK_NAME,),
        include_formula_without_cache=True,
    )
    assert is_effectively_empty_row(
        values,
        key_columns=(LogicalColumn.WORK_NAME,),
        include_formula_without_cache=False,
    )


def test_excel_error_is_not_an_empty_key_value(
    workbook_session_factory,
    schema_factory,
):
    schema = schema_factory(
        "СВВР",
        SheetType.SVVR,
        [LogicalColumn.CURRENT_PERIOD_QUANTITY],
    )
    with workbook_session_factory({"СВВР": [["Количество"], ["#DIV/0!"]]}) as (
        session,
        _,
    ):
        value = extract_cell_value(
            session,
            sheet_name="СВВР",
            row_number=2,
            column_resolution=schema.columns[0],
            sheet_type=SheetType.SVVR,
        )
    assert not is_effectively_empty_row(
        (value,),
        key_columns=(LogicalColumn.CURRENT_PERIOD_QUANTITY,),
    )


def test_non_contiguous_resolved_columns_are_streamed(
    workbook_session_factory,
    schema_factory,
):
    header = ["Наименование", *([None] * 24), "Количество"]
    data = ["Работа", *(["не читать"] * 24), 7]
    schema = schema_factory(
        "КС-2",
        SheetType.KS2,
        [LogicalColumn.WORK_NAME, LogicalColumn.CURRENT_PERIOD_QUANTITY],
        physical_columns=[1, 26],
    )
    with workbook_session_factory({"КС-2": [header, data]}) as (session, _):
        plan = build_extraction_plan(session, schema, ExtractionConfig())
        numbers = list(
            iter_source_row_numbers(
                session,
                plan,
                ExtractionConfig(),
            )
        )
    assert numbers == [2]
