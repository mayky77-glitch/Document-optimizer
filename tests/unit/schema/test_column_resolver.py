from openpyxl.utils.cell import column_index_from_string

from report_processor.schema.column_aliases import DEFAULT_COLUMN_ALIASES
from report_processor.schema.column_resolver import resolve_logical_columns
from report_processor.schema.models import ComposedHeader, LogicalColumn, SheetType
from report_processor.schema.text_normalization import normalize_header_text


def header(column: str, text: str) -> ComposedHeader:
    return ComposedHeader(
        column_index=column_index_from_string(column),
        column_letter=column,
        parts=(text,),
        raw_text=text,
        normalized_text=normalize_header_text(text),
        is_empty=False,
        source_coordinates=(f"{column}1",),
        merged_sources=(),
    )


def resolved_map(headers: tuple[ComposedHeader, ...]):
    values = resolve_logical_columns(headers, SheetType.KS6A, DEFAULT_COLUMN_ALIASES)
    return {item.logical_column: item for item in values}


def test_quantity_and_cost_contexts_are_distinguished() -> None:
    values = resolved_map(
        (
            header("A", "Наименование этапа выполнения работ"),
            header("B", "Ед. изм."),
            header("C", "Количество по проекту"),
            header("D", "Выполнено за июль 2026 Количество"),
            header("E", "Выполнено с начала строительства Количество"),
            header("F", "Остаток количества"),
            header("G", "Цена за единицу"),
            header("H", "Стоимость за июль 2026"),
            header("I", "Стоимость с начала строительства"),
            header("J", "Общая стоимость"),
        )
    )
    assert values[LogicalColumn.CONTRACT_QUANTITY].column_letter == "C"
    assert values[LogicalColumn.CURRENT_PERIOD_QUANTITY].column_letter == "D"
    assert values[LogicalColumn.CUMULATIVE_QUANTITY].column_letter == "E"
    assert values[LogicalColumn.REMAINING_QUANTITY].column_letter == "F"
    assert values[LogicalColumn.UNIT_PRICE].column_letter == "G"
    assert values[LogicalColumn.CURRENT_PERIOD_COST].column_letter == "H"
    assert values[LogicalColumn.CUMULATIVE_COST].column_letter == "I"
    assert values[LogicalColumn.TOTAL_COST].column_letter == "J"


def test_duplicate_equal_headers_are_ambiguous() -> None:
    values = resolved_map(
        (
            header("A", "Наименование работ"),
            header("B", "Единица измерения"),
            header("C", "Количество за месяц"),
            header("D", "Количество за месяц"),
        )
    )
    result = values[LogicalColumn.CURRENT_PERIOD_QUANTITY]
    assert result.status == "AMBIGUOUS_COLUMN"
    assert result.column_index is None
    assert {item.column_letter for item in result.alternatives[:2]} == {"C", "D"}


def test_generic_quantity_and_cost_are_not_assigned_to_period_fields() -> None:
    values = resolved_map(
        (
            header("A", "Наименование работ"),
            header("B", "Единица измерения"),
            header("C", "Количество"),
            header("D", "Стоимость"),
        )
    )
    assert values[LogicalColumn.CURRENT_PERIOD_QUANTITY].status == "COLUMN_NOT_FOUND"
    assert values[LogicalColumn.CUMULATIVE_QUANTITY].status == "COLUMN_NOT_FOUND"
    assert values[LogicalColumn.CURRENT_PERIOD_COST].status == "COLUMN_NOT_FOUND"
    assert values[LogicalColumn.CUMULATIVE_COST].status == "COLUMN_NOT_FOUND"


def test_reporting_period_volume_with_inflected_token_resolves_without_conflict() -> None:
    values = resolved_map(
        (
            header("A", "Наименование работ"),
            header("I", "Объем выполненных работ В отчетном периоде"),
            header("J", "Объем выполненных работ с начала строительства"),
        )
    )
    result = values[LogicalColumn.CURRENT_PERIOD_QUANTITY]
    assert result.status == "OK"
    assert result.column_letter == "I"
    assert "PHYSICAL_COLUMN_CONFLICT" not in result.warnings
