from __future__ import annotations

from report_processor.extraction import extract_cell_value
from report_processor.schema import ColumnResolution, LogicalColumn, SheetType


def _column(column: int, logical: LogicalColumn) -> ColumnResolution:
    from openpyxl.utils.cell import get_column_letter

    return ColumnResolution(
        logical, column, get_column_letter(column), logical.value, 1.0, "fixture", (), "OK"
    )


def test_literal_and_zero_are_preserved(workbook_session_factory):
    with workbook_session_factory({"КС-2": [["name", "qty"], ["Работа", 0]]}) as (session, _):
        value = extract_cell_value(
            session,
            sheet_name="КС-2",
            row_number=2,
            column_resolution=_column(2, LogicalColumn.CURRENT_PERIOD_QUANTITY),
            sheet_type=SheetType.KS2,
        )
    assert value.effective_value == 0
    assert value.effective_value_source == "literal"
    assert value.status == "OK"
    assert not value.is_empty
    assert value.provenance.location.coordinate == "B2"


def test_formula_without_cache_is_not_calculated(workbook_session_factory):
    rows = {"КС-6а": [[10], [20], [None]]}
    with workbook_session_factory(rows, formulas={("КС-6а", "A3"): "=SUM(A1:A2)"}) as (session, _):
        value = extract_cell_value(
            session,
            sheet_name="КС-6а",
            row_number=3,
            column_resolution=_column(1, LogicalColumn.CUMULATIVE_QUANTITY),
            sheet_type=SheetType.KS6A,
        )
    assert value.raw_formula_value == "=SUM(A1:A2)"
    assert value.raw_cached_value is None
    assert value.effective_value is None
    assert value.effective_value_source == "formula_without_cache"
    assert value.status == "FORMULA_WITHOUT_CACHED_VALUE"
    assert value.provenance.formula == "=SUM(A1:A2)"


def test_excel_error_is_separate(workbook_session_factory):
    with workbook_session_factory({"КС-2": [["#DIV/0!"]]}) as (session, _):
        value = extract_cell_value(
            session,
            sheet_name="КС-2",
            row_number=1,
            column_resolution=_column(1, LogicalColumn.CURRENT_PERIOD_COST),
            sheet_type=SheetType.KS2,
        )
    assert value.effective_value is None
    assert value.effective_value_source == "excel_error"
    assert value.status == "EXCEL_ERROR"
    assert value.is_error
    assert not value.is_empty


def test_empty_literal_is_empty(workbook_session_factory):
    with workbook_session_factory({"КС-2": [[None]]}) as (session, _):
        value = extract_cell_value(
            session,
            sheet_name="КС-2",
            row_number=1,
            column_resolution=_column(1, LogicalColumn.WORK_NAME),
            sheet_type=SheetType.KS2,
        )
    assert value.status == "EMPTY"
    assert value.is_empty
    assert value.effective_value_source == "empty"


def test_cached_formula_zero_is_available():
    from types import SimpleNamespace

    from report_processor.extraction.cell_values import extract_cell_pair_value

    session = SimpleNamespace(source_file_id="file", filename="book.xlsx")
    value = extract_cell_pair_value(
        session,
        sheet_name="КС-6а",
        row_number=10,
        column_resolution=_column(1, LogicalColumn.CURRENT_PERIOD_QUANTITY),
        formula_cell=SimpleNamespace(value="=A1-A2", data_type="f"),
        cached_cell=SimpleNamespace(value=0, data_type="n"),
        sheet_type=SheetType.KS6A,
    )
    assert value.effective_value == 0
    assert value.effective_value_source == "cached_formula_value"
    assert value.status == "FORMULA_WITH_CACHED_VALUE"
    assert value.provenance.cached_value_available


def test_text_that_looks_like_excel_error_remains_literal():
    from types import SimpleNamespace

    from report_processor.extraction.cell_values import extract_cell_pair_value

    session = SimpleNamespace(source_file_id="file", filename="book.xlsx")
    value = extract_cell_pair_value(
        session,
        sheet_name="КС-2",
        row_number=2,
        column_resolution=_column(1, LogicalColumn.WORK_NAME),
        formula_cell=SimpleNamespace(value="#NAME?", data_type="s"),
        cached_cell=SimpleNamespace(value="#NAME?", data_type="s"),
        sheet_type=SheetType.KS2,
    )
    assert value.effective_value == "#NAME?"
    assert value.status == "OK"
    assert not value.is_error


def test_array_formula_is_normalized_for_provenance_and_jsonl(tmp_path):
    from types import SimpleNamespace

    from openpyxl.worksheet.formula import ArrayFormula

    from report_processor.extraction.cell_values import extract_cell_pair_value
    from report_processor.extraction.models import CanonicalSourceRow, SourceLocation
    from report_processor.extraction.serialization import save_rows_jsonl

    cell = extract_cell_pair_value(
        SimpleNamespace(source_file_id="file", filename="book.xlsx"),
        sheet_name="КС-2 Логистика",
        row_number=62,
        column_resolution=_column(7, LogicalColumn.WORK_NAME),
        formula_cell=SimpleNamespace(value=ArrayFormula("G62", "=#REF!"), data_type="f"),
        cached_cell=SimpleNamespace(value=None, data_type="n"),
        sheet_type=SheetType.KS2,
    )
    assert cell.raw_formula_value == "=#REF!"
    assert cell.provenance.formula == "=#REF!"
    assert cell.effective_value is None
    row = CanonicalSourceRow(
        "id",
        "ks2",
        SourceLocation("file", "book.xlsx", "КС-2 Логистика", "ks2", 62),
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        (cell,),
        "PARTIAL",
        cell.warnings,
    )
    saved = save_rows_jsonl((row,), tmp_path / "rows.jsonl")
    assert saved.row_count == 1
