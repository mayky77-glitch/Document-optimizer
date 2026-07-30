from __future__ import annotations

from decimal import Decimal

from report_processor.adapters import KS2Adapter
from report_processor.extraction import ExtractionConfig, extract_worksheet_rows
from report_processor.schema import LogicalColumn, SheetType


def test_ks2_rows_are_mapped_without_calculations(workbook_session_factory, schema_factory):
    headers = [
        "Позиция",
        "Наименование работ и затрат",
        "Ед. изм.",
        "Количество",
        "Цена за единицу",
        "Стоимость",
    ]
    rows = [
        headers,
        ["001", "Монтаж", "м", "2,5", "100,00", None],
        [None, "Работа без позиции", None, None, None, None],
        ["003", "Нулевая работа", "шт", 0, 5, 0],
        ["004", "Корректировка", "шт", "-1,25", 10, "-12,50"],
        headers,
        [None, None, None, None, None, None],
    ]
    schema = schema_factory(
        "КС-2",
        SheetType.KS2,
        [
            LogicalColumn.POSITION_CODE,
            LogicalColumn.WORK_NAME,
            LogicalColumn.UNIT,
            LogicalColumn.CURRENT_PERIOD_QUANTITY,
            LogicalColumn.UNIT_PRICE,
            LogicalColumn.CURRENT_PERIOD_COST,
        ],
        headers=headers,
    )
    with workbook_session_factory({"КС-2": rows}) as (session, _):
        result = extract_worksheet_rows(
            session,
            schema,
            document_index="1006 (682)",
            document_period="2026-07",
            config=ExtractionConfig(max_consecutive_empty_rows=1),
        )
    assert result.extracted_row_count == 4
    assert result.skipped_header_row_count == 1
    first = result.rows[0]
    assert first.position_code_raw == "001"
    assert first.current_period_quantity == Decimal("2.5")
    assert first.unit_price == Decimal("100.00")
    assert first.current_period_cost is None
    assert first.total_cost is None
    assert first.document_index == "1006 (682)"
    assert len(first.source_values) == 6
    assert all(item.provenance.location.coordinate for item in first.source_values)
    assert result.rows[1].position_code_raw is None
    assert result.rows[2].current_period_quantity == Decimal("0")
    assert result.rows[3].current_period_quantity == Decimal("-1.25")


def test_ks2_formula_without_cache_is_preserved(workbook_session_factory, schema_factory):
    rows = [["Наименование", "Количество", "Цена", "Стоимость"], ["Работа", 2, 10, None]]
    schema = schema_factory(
        "КС-2",
        SheetType.KS2,
        [
            LogicalColumn.WORK_NAME,
            LogicalColumn.CURRENT_PERIOD_QUANTITY,
            LogicalColumn.UNIT_PRICE,
            LogicalColumn.CURRENT_PERIOD_COST,
        ],
    )
    with workbook_session_factory(
        {"КС-2": rows},
        formulas={("КС-2", "D2"): "=B2*C2"},
    ) as (session, _):
        result = extract_worksheet_rows(
            session,
            schema,
            document_index=None,
            document_period=None,
            config=ExtractionConfig(max_consecutive_empty_rows=2),
        )
    row = result.rows[0]
    assert row.current_period_cost is None
    cost_cell = next(
        item for item in row.source_values if item.logical_column == "current_period_cost"
    )
    assert cost_cell.raw_formula_value == "=B2*C2"
    assert cost_cell.effective_value is None
    assert cost_cell.status == "FORMULA_WITHOUT_CACHED_VALUE"
    assert row.status == "PARTIAL"


def test_ks2_schema_validation_requires_only_work_name(schema_factory):
    adapter = KS2Adapter()
    valid = schema_factory("КС-2", SheetType.KS2, [LogicalColumn.WORK_NAME])
    invalid = schema_factory("КС-2", SheetType.KS2, [LogicalColumn.UNIT])
    assert adapter.validate_schema(valid).valid
    result = adapter.validate_schema(invalid)
    assert not result.valid
    assert result.status == "REQUIRED_COLUMNS_MISSING"
