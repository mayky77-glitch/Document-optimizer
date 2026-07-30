from pathlib import Path

import pytest

from conftest import regular_entry
from report_processor.domain.exceptions import CellReadError
from report_processor.domain.statuses import StatusCode
from report_processor.excel.cell_reader import (
    normalize_cell_coordinate,
    read_cell_snapshot,
    read_cell_snapshots,
)
from report_processor.excel.models import CellReference, WorkbookOpenRequest
from report_processor.excel.workbook_session import open_dual_workbook
from report_processor.materialization.regular_file import resolve_regular_file


def _session(workbook_path: Path):
    source = resolve_regular_file(regular_entry(workbook_path), max_file_size_bytes=10**7)
    return open_dual_workbook(WorkbookOpenRequest(source))


def test_coordinate_validation():
    assert normalize_cell_coordinate("a1") == "A1"
    assert normalize_cell_coordinate("XFD1048576") == "XFD1048576"
    for value in ("A0", "XFE1", "A1048577", "1A", "A 1", ""):
        with pytest.raises(CellReadError):
            normalize_cell_coordinate(value)


def test_reads_numbers_strings_empty_formula_and_error(workbook_path: Path):
    with _session(workbook_path) as session:
        number = read_cell_snapshot(session, "Данные", "A1")
        text = read_cell_snapshot(session, "Данные", "B1")
        empty = read_cell_snapshot(session, "Данные", "C1")
        formula = read_cell_snapshot(session, "Данные", "A3")
        lookalike = read_cell_snapshot(session, "Данные", "D1")
        real_error = read_cell_snapshot(session, "Данные", "E1")

    assert number.formula_value == 10 and number.status == StatusCode.OK.value
    assert text.formula_value == "т"
    assert empty.formula_value is None and empty.cached_value is None
    assert formula.formula_value == "=SUM(A1:A2)"
    assert formula.cached_value is None
    assert formula.status == StatusCode.FORMULA_WITHOUT_CACHED_VALUE.value
    assert lookalike.status == StatusCode.OK.value and lookalike.formula_error is None
    assert real_error.status == StatusCode.REAL_EXCEL_ERROR.value


def test_missing_sheet_and_invalid_coordinate(workbook_path: Path):
    with _session(workbook_path) as session:
        with pytest.raises(CellReadError) as missing:
            read_cell_snapshot(session, "Нет", "A1")
        with pytest.raises(CellReadError) as invalid:
            read_cell_snapshot(session, "Данные", "BAD")
    assert missing.value.status == StatusCode.SHEET_NOT_FOUND
    assert invalid.value.status == StatusCode.INVALID_CELL_COORDINATE


def test_batch_preserves_order_duplicates_and_limit(workbook_path: Path):
    requests = [
        CellReference("Данные", "A1"),
        CellReference("Данные", "B1"),
        CellReference("Данные", "A1"),
    ]
    with _session(workbook_path) as session:
        result = read_cell_snapshots(session, requests)
        assert [snapshot.coordinate for snapshot in result] == ["A1", "B1", "A1"]
        with pytest.raises(ValueError):
            read_cell_snapshots(session, requests, max_cells=2)
