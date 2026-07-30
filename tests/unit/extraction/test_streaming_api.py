from __future__ import annotations

import json
from pathlib import Path

import pytest

from report_processor.extraction import (
    ExtractionConfig,
    ExtractionSerializationError,
    build_extraction_metadata,
    create_workbook_extraction_stream,
    save_rows_jsonl,
)
from report_processor.schema import LogicalColumn, SheetType, WorkbookSchema


def test_workbook_jsonl_stream_does_not_retain_rows(
    tmp_path: Path,
    workbook_session_factory,
    schema_factory,
):
    rows = {
        "КС-2": [["Наименование", "Количество"], ["Работа 1", 0], ["Работа 2", 2]],
        "СВВР": [["Наименование", "Количество"], ["Работа 3", "3,5"]],
    }
    schema = WorkbookSchema(
        source_file_id="file-001",
        filename="source.xlsx",
        worksheets=(
            schema_factory(
                "КС-2",
                SheetType.KS2,
                [LogicalColumn.WORK_NAME, LogicalColumn.CURRENT_PERIOD_QUANTITY],
            ),
            schema_factory(
                "СВВР",
                SheetType.SVVR,
                [LogicalColumn.WORK_NAME, LogicalColumn.CURRENT_PERIOD_QUANTITY],
            ),
        ),
        sheets_by_type={},
        primary_sheets={},
        confidence=1.0,
        status="OK",
    )
    output = tmp_path / "rows.jsonl"
    with workbook_session_factory(rows) as (session, _):
        stream = create_workbook_extraction_stream(
            session,
            schema,
            document_index="1006 (682)",
            document_period="2026-07",
            config=ExtractionConfig(),
        )
        result = save_rows_jsonl(
            stream,
            output,
            metadata_factory=lambda _count: build_extraction_metadata(stream.sheet_results),
        )

    assert result.row_count == 3
    assert stream.finished
    assert len(stream.sheet_results) == 2
    assert all(not item.rows for item in stream.sheet_results)
    payloads = [json.loads(line) for line in output.read_text().splitlines()]
    assert [item["work_name_raw"] for item in payloads] == [
        "Работа 1",
        "Работа 2",
        "Работа 3",
    ]
    assert payloads[0]["current_period_quantity"] == "0"
    meta = json.loads(output.with_suffix(".meta.json").read_text())
    assert meta["total_rows"] == 3
    assert [item["sheet_name"] for item in meta["sheet_results"]] == ["КС-2", "СВВР"]


def test_metadata_factory_failure_removes_temporary_output(tmp_path: Path):
    output = tmp_path / "rows.jsonl"

    def broken_factory(_count: int):
        raise ValueError("bad metadata")

    with pytest.raises(ExtractionSerializationError, match="bad metadata"):
        save_rows_jsonl((), output, metadata_factory=broken_factory)

    assert not output.exists()
    assert not output.with_suffix(".meta.json").exists()
    assert not list(tmp_path.glob(".rows.jsonl.*.tmp"))
