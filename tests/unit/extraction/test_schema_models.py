import json

import pytest

from report_processor.extraction import load_workbook_schema_json
from report_processor.extraction.exceptions import ExtractionSchemaError
from report_processor.schema import LogicalColumn, SheetType


def test_schema_loader_reads_block_five_columns(tmp_path):
    payload = {
        "file_id": "f1",
        "source_filename": "book.xlsx",
        "worksheets": [
            {
                "name": "СВВР",
                "type": "СВВР",
                "header_range": {"start_row": 2, "end_row": 4},
                "column_resolutions": {
                    "work_name": {"column_index": 5, "column_letter": "E", "header_text": "Работы"},
                },
            }
        ],
    }
    payload["worksheets"][0]["columns"] = [
        {"logical_column": "work_name", "column_index": 5, "column_letter": "E", "status": "OK"}
    ]
    payload["worksheets"][0]["sheet_name"] = payload["worksheets"][0].pop("name")
    payload["worksheets"][0]["sheet_type"] = "svvr"
    path = tmp_path / "schema.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    schema = load_workbook_schema_json(path)
    assert schema.source_file_id == "f1"
    assert schema.worksheets[0].sheet_type is SheetType.SVVR
    assert schema.worksheets[0].columns[0].logical_column is LogicalColumn.WORK_NAME


def test_schema_loader_skips_unresolved_block_five_columns(tmp_path):
    path = tmp_path / "schema.json"
    payload = {
        "worksheets": [
            {
                "sheet_name": "КС-2",
                "sheet_type": "ks2",
                "data_start_row": 2,
                "columns": [
                    {"logical_column": "work_name", "column_index": 1, "status": "OK"},
                    {"logical_column": "unit", "column_index": None, "status": "COLUMN_NOT_FOUND"},
                ],
            }
        ]
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    columns = load_workbook_schema_json(path).worksheets[0].columns
    assert [item.logical_column for item in columns] == [LogicalColumn.WORK_NAME]
    payload["worksheets"][0]["columns"][1]["column_index"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ExtractionSchemaError, match="COLUMN_INDEX_INVALID"):
        load_workbook_schema_json(path)


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("header_start_row", "1", "HEADER_START_ROW_INVALID"),
        ("header_end_row", True, "HEADER_END_ROW_INVALID"),
        ("data_start_row", "2", "DATA_START_ROW_INVALID"),
        ("first_table_column", 0, "FIRST_TABLE_COLUMN_INVALID"),
        ("last_table_column", -1, "LAST_TABLE_COLUMN_INVALID"),
    ],
)
def test_schema_loader_rejects_invalid_row_and_column_indexes(tmp_path, field, value, error):
    payload = {
        "worksheets": [
            {
                "sheet_name": "КС-2",
                "sheet_type": "ks2",
                "columns": [],
                field: value,
            }
        ]
    }
    path = tmp_path / "schema.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ExtractionSchemaError, match=error):
        load_workbook_schema_json(path)


@pytest.mark.parametrize(
    "payload",
    [
        {"worksheets": "not-a-list"},
        {"worksheets": ["not-a-mapping"]},
        {"worksheets": [{"sheet_name": "КС-2", "sheet_type": "ks2", "columns": ["bad"]}]},
        {"worksheets": [], "sheets_by_type": []},
        {"worksheets": [], "primary_sheets": []},
        {"worksheets": [], "warnings": None},
        {"worksheets": [], "warnings": "warning"},
        {"worksheets": [], "confidence": "high"},
    ],
)
def test_schema_loader_rejects_malformed_consumed_collections_and_values(tmp_path, payload):
    path = tmp_path / "schema.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ExtractionSchemaError):
        load_workbook_schema_json(path)


@pytest.mark.parametrize("invalid_index", [-1, 0, True, "1"])
def test_schema_loader_rejects_invalid_resolved_column_indexes(tmp_path, invalid_index):
    payload = {
        "worksheets": [
            {
                "sheet_name": "КС-2",
                "sheet_type": "ks2",
                "columns": [
                    {
                        "logical_column": "work_name",
                        "column_index": invalid_index,
                        "status": "OK",
                    }
                ],
            }
        ]
    }
    path = tmp_path / "schema.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ExtractionSchemaError, match="COLUMN_INDEX_INVALID"):
        load_workbook_schema_json(path)


@pytest.mark.parametrize(
    ("column", "error"),
    [
        (
            {
                "logical_column": "unit",
                "column_index": None,
                "status": "COLUMN_NOT_FOUND",
                "confidence": "high",
            },
            "COLUMN_CONFIDENCE_INVALID",
        ),
        (
            {
                "logical_column": "unit",
                "column_index": None,
                "status": "COLUMN_NOT_FOUND",
                "warnings": None,
            },
            "COLUMN_WARNINGS_INVALID",
        ),
        (
            {
                "logical_column": "unit",
                "column_index": None,
                "status": "COLUMN_NOT_FOUND",
                "confidence": 10**400,
            },
            "COLUMN_CONFIDENCE_INVALID",
        ),
    ],
)
def test_schema_loader_validates_unresolved_column_fields(tmp_path, column, error):
    payload = {
        "worksheets": [
            {
                "sheet_name": "КС-2",
                "sheet_type": "ks2",
                "columns": [column],
            }
        ]
    }
    path = tmp_path / "schema.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ExtractionSchemaError, match=error):
        load_workbook_schema_json(path)
