from __future__ import annotations

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


def test_number_sign_p_alias_resolves_to_row_number_for_position_fallback() -> None:
    resolutions = resolve_logical_columns(
        (header("A", "№ п/п"), header("B", "Наименование работ")),
        SheetType.KS2,
        DEFAULT_COLUMN_ALIASES,
    )
    by_logical = {item.logical_column: item for item in resolutions}

    assert by_logical[LogicalColumn.ROW_NUMBER].status == "OK"
    assert by_logical[LogicalColumn.ROW_NUMBER].column_letter == "A"
