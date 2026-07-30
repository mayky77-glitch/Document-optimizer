from __future__ import annotations

from decimal import Decimal

from report_processor.extraction import ExtractionConfig, extract_worksheet_rows
from report_processor.schema import LogicalColumn, SheetType


def test_ks6a_all_available_values_and_provenance(workbook_session_factory, schema_factory):
    headers = [
        "Наименование",
        "Ед.",
        "Договорное количество",
        "Текущее количество",
        "Накопительное количество",
        "Остаток",
        "Цена",
        "Договорная стоимость",
        "Текущая стоимость",
        "Накопительная стоимость",
    ]
    rows = [
        headers,
        ["Работа", "м", "100", "10,5", "55,5", "44,5", "123.45", "12345", "1296,225", "6851,475"],
        ["Ноль", None, 0, 0, 0, 0, 0, 0, 0, 0],
        ["Корректировка", "шт", -1, "-2,5", "-3,5", 1, 10, -10, -25, -35],
    ]
    logical = [
        LogicalColumn.WORK_NAME,
        LogicalColumn.UNIT,
        LogicalColumn.CONTRACT_QUANTITY,
        LogicalColumn.CURRENT_PERIOD_QUANTITY,
        LogicalColumn.CUMULATIVE_QUANTITY,
        LogicalColumn.REMAINING_QUANTITY,
        LogicalColumn.UNIT_PRICE,
        LogicalColumn.CONTRACT_COST,
        LogicalColumn.CURRENT_PERIOD_COST,
        LogicalColumn.CUMULATIVE_COST,
    ]
    schema = schema_factory("КС-6а", SheetType.KS6A, logical, headers=headers)
    with workbook_session_factory({"КС-6а": rows}) as (session, _):
        result = extract_worksheet_rows(
            session,
            schema,
            document_index=None,
            document_period=None,
        )
    assert result.extracted_row_count == 3
    row = result.rows[0]
    assert row.contract_quantity == Decimal("100")
    assert row.current_period_quantity == Decimal("10.5")
    assert row.cumulative_quantity == Decimal("55.5")
    assert row.remaining_quantity == Decimal("44.5")
    assert row.unit_price == Decimal("123.45")
    assert row.current_period_cost == Decimal("1296.225")
    assert row.cumulative_cost == Decimal("6851.475")
    assert all(item.provenance.location.sheet_name == "КС-6а" for item in row.source_values)
    assert result.rows[1].current_period_quantity == Decimal("0")
    assert result.rows[2].current_period_quantity == Decimal("-2.5")


def test_ks6a_formula_without_cache_and_large_decimal(workbook_session_factory, schema_factory):
    rows = [
        ["Наименование", "Текущее количество", "Накопительное количество"],
        ["Большая работа", "12345678901234567890,123456789", None],
    ]
    schema = schema_factory(
        "КС-6а",
        SheetType.KS6A,
        [
            LogicalColumn.WORK_NAME,
            LogicalColumn.CURRENT_PERIOD_QUANTITY,
            LogicalColumn.CUMULATIVE_QUANTITY,
        ],
    )
    with workbook_session_factory(
        {"КС-6а": rows},
        formulas={("КС-6а", "C2"): "=B2"},
    ) as (session, _):
        result = extract_worksheet_rows(
            session,
            schema,
            document_index=None,
            document_period=None,
        )
    row = result.rows[0]
    assert row.current_period_quantity == Decimal("12345678901234567890.123456789")
    assert row.cumulative_quantity is None
    formula_cell = row.source_values[2]
    assert formula_cell.raw_formula_value == "=B2"
    assert formula_cell.provenance.formula == "=B2"


def test_ks6a_empty_limit_and_max_rows(workbook_session_factory, schema_factory):
    rows = [["Наименование"]] + [[f"Работа {i}"] for i in range(10)]
    schema = schema_factory("КС-6а", SheetType.KS6A, [LogicalColumn.WORK_NAME])
    with workbook_session_factory({"КС-6а": rows}) as (session, _):
        result = extract_worksheet_rows(
            session,
            schema,
            document_index=None,
            document_period=None,
            config=ExtractionConfig(max_rows=3),
        )
    assert result.scanned_row_count == 3
    assert result.extracted_row_count == 3
    assert result.stop_reason == "row_limit_reached"
    assert result.status == "ROW_LIMIT_REACHED"
