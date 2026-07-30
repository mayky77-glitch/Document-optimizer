from __future__ import annotations

import hashlib
from pathlib import Path

from openpyxl import Workbook

from report_processor.extraction import extract_worksheet_rows
from report_processor.inventory.file_manifest import build_file_manifest
from report_processor.schema import LogicalColumn, SheetType
from report_processor.selection.models import SourceCandidate
from report_processor.workflow import prepared_workbook_session


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_source_workbook_is_unchanged_and_both_books_close(tmp_path: Path, schema_factory):
    path = tmp_path / "source.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "КС-2"
    sheet.append(["Наименование", "Количество"])
    sheet.append(["Работа", 1])
    workbook.save(path)
    workbook.close()
    before = _digest(path)
    schema = schema_factory(
        "КС-2", SheetType.KS2, [LogicalColumn.WORK_NAME, LogicalColumn.CURRENT_PERIOD_QUANTITY]
    )
    entry = build_file_manifest(path).entries[0]
    candidate = SourceCandidate(entry.file_id, entry, 0, None, True, (), (), ())
    with prepared_workbook_session(candidate) as session:
        formula_book = session.formula_workbook
        cached_book = session.values_workbook
        result = extract_worksheet_rows(
            session,
            schema,
            document_index=None,
            document_period=None,
        )
        assert result.extracted_row_count == 1
    assert _digest(path) == before
    assert formula_book._archive.fp is None
    assert cached_book._archive.fp is None
