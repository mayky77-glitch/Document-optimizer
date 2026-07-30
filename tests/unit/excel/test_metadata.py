from pathlib import Path

from conftest import regular_entry
from report_processor.excel.models import WorkbookOpenRequest
from report_processor.excel.workbook_metadata import (
    collect_workbook_metadata,
    collect_worksheet_metadata,
)
from report_processor.excel.workbook_session import open_dual_workbook
from report_processor.materialization.regular_file import resolve_regular_file


def test_collects_workbook_and_reported_sheet_metadata(workbook_path: Path):
    source = resolve_regular_file(regular_entry(workbook_path), max_file_size_bytes=10**7)
    with open_dual_workbook(WorkbookOpenRequest(source)) as session:
        workbook = collect_workbook_metadata(session)
        worksheets = collect_worksheet_metadata(session)
    assert workbook.sheet_names == ("Данные", "Скрытый", "Очень скрытый")
    assert workbook.has_hidden_sheets
    assert workbook.has_very_hidden_sheets
    assert worksheets[0].max_row_reported >= 3
    assert worksheets[0].max_column_reported >= 5
    assert "REPORTED_DIMENSIONS" in worksheets[0].warnings[0]
