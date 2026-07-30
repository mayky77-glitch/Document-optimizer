from __future__ import annotations

import os
from pathlib import Path

import pytest
from openpyxl import Workbook

from report_processor.extraction import ExtractionConfig, extract_worksheet_rows
from report_processor.inventory.file_manifest import build_file_manifest
from report_processor.schema import LogicalColumn, SheetType
from report_processor.selection.models import SourceCandidate
from report_processor.workflow import prepared_workbook_session


@pytest.mark.slow
@pytest.mark.skipif(os.getenv("RUN_SLOW") != "1", reason="set RUN_SLOW=1 to run 50k-row test")
def test_streaming_50k_rows(tmp_path: Path, schema_factory):
    path = tmp_path / "large.xlsx"
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("КС-2")
    sheet.append(["Наименование", "Количество"])
    for index in range(50_000):
        sheet.append([f"Работа {index}", index])
    workbook.save(path)
    entry = build_file_manifest(path).entries[0]
    candidate = SourceCandidate(entry.file_id, entry, 0, None, True, (), (), ())
    schema = schema_factory(
        "КС-2", SheetType.KS2, [LogicalColumn.WORK_NAME, LogicalColumn.CURRENT_PERIOD_QUANTITY]
    )
    with prepared_workbook_session(candidate) as session:
        result = extract_worksheet_rows(
            session,
            schema,
            document_index=None,
            document_period=None,
            config=ExtractionConfig(max_rows=50_000, max_consecutive_empty_rows=20),
        )
    assert result.extracted_row_count == 50_000
    assert result.scanned_row_count == 50_000
