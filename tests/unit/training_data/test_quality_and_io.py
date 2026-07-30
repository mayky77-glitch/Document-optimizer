import json
from dataclasses import asdict, replace
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from report_processor.extraction.models import (
    CanonicalSourceRow,
    ExtractedCellValue,
    SourceLocation,
    ValueProvenance,
)
from report_processor.extraction.statuses import CellValueStatus
from report_processor.storage import DuckDBStore, StorageError, StorageSchemaError
from report_processor.training_data import (
    FormulaErrorCode,
    TrainingDataConfig,
    load_canonical_rows_duckdb,
    load_canonical_rows_jsonl,
    prepare_training_data,
    resolve_input_format,
)


def make_source_row(status: str) -> CanonicalSourceRow:
    location = SourceLocation(
        source_file_id="file",
        filename="КС-6а.xlsx",
        sheet_name="КС-6а",
        sheet_type="ks6a",
        row_number=42,
        column_number=5,
        column_letter="E",
        coordinate="E42",
    )
    provenance = ValueProvenance(
        location=location,
        logical_column="current_period_quantity",
        header_text="Количество",
        formula="=VLOOKUP(A42,СВВР!A:E,5,0)",
        cached_value_available=status == CellValueStatus.FORMULA_WITH_CACHED_VALUE.value,
        value_source="cached_formula_value",
        warnings=(),
    )
    cell = ExtractedCellValue(
        logical_column="current_period_quantity",
        coordinate="E42",
        raw_formula_value="=VLOOKUP(A42,СВВР!A:E,5,0)",
        raw_cached_value="12.5",
        effective_value="12.5",
        effective_value_source="cached_formula_value",
        formula_data_type="f",
        cached_data_type="n",
        is_formula=True,
        is_empty=False,
        is_error=status
        in {
            CellValueStatus.EXCEL_ERROR.value,
            CellValueStatus.VALUE_READ_FAILED.value,
        },
        status=status,
        warnings=(),
        provenance=provenance,
    )
    return CanonicalSourceRow(
        row_id="row",
        source_type="ks6a",
        source_location=replace(
            location,
            column_number=None,
            column_letter=None,
            coordinate=None,
        ),
        document_index="0918 (687)",
        document_period="2026-06",
        object_code_raw="ОБ-1",
        object_name_raw=None,
        subobject_code_raw=None,
        subobject_name_raw=None,
        position_code_raw="15",
        work_name_raw="Монтаж трубопровода",
        unit_raw="м",
        contract_quantity=None,
        current_period_quantity=Decimal("12.5"),
        cumulative_quantity=None,
        remaining_quantity=None,
        unit_price=None,
        contract_cost=None,
        current_period_cost=None,
        cumulative_cost=None,
        total_cost=None,
        basis_code_raw=None,
        drawing_code_raw=None,
        cost_type_code_raw=None,
        source_values=(cell,),
        status="OK",
        warnings=(),
    )


def test_cached_formula_is_not_an_error():
    result = prepare_training_data(
        (make_source_row(CellValueStatus.FORMULA_WITH_CACHED_VALUE.value),)
    )
    assert result.rows[0].formula_error is FormulaErrorCode.NONE


def test_excel_error_is_excluded_by_default_and_can_be_retained():
    source = make_source_row(CellValueStatus.EXCEL_ERROR.value)
    default = prepare_training_data((source,))
    assert default.statistics.skipped_formula_error_rows == 1
    retained = prepare_training_data(
        (source,),
        config=TrainingDataConfig(include_critical_formula_errors=True),
    )
    assert retained.rows[0].formula_error is FormulaErrorCode.EXCEL_ERROR


def test_jsonl_loader_restores_decimal_values(tmp_path: Path):
    source = make_source_row(CellValueStatus.FORMULA_WITH_CACHED_VALUE.value)
    payload = asdict(source)
    for field in (
        "contract_quantity",
        "current_period_quantity",
        "cumulative_quantity",
        "remaining_quantity",
        "unit_price",
        "contract_cost",
        "current_period_cost",
        "cumulative_cost",
        "total_cost",
    ):
        value = payload[field]
        payload[field] = str(value) if value is not None else None
    path = tmp_path / "rows.jsonl"
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    restored = load_canonical_rows_jsonl(path)
    assert restored[0].current_period_quantity == Decimal("12.5")


def test_jsonl_loader_rejects_coerced_boolean(tmp_path: Path):
    source = make_source_row(CellValueStatus.FORMULA_WITH_CACHED_VALUE.value)
    payload = asdict(source)
    payload["source_values"][0]["is_formula"] = "false"
    path = tmp_path / "rows.jsonl"
    path.write_text(json.dumps(payload, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="строка JSONL 1"):
        load_canonical_rows_jsonl(path)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "not-a-decimal"])
def test_jsonl_loader_rejects_invalid_decimal_values(tmp_path: Path, value: str):
    source = make_source_row(CellValueStatus.FORMULA_WITH_CACHED_VALUE.value)
    payload = asdict(source)
    payload["current_period_quantity"] = value
    path = tmp_path / "rows.jsonl"
    path.write_text(json.dumps(payload, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="строка JSONL 1"):
        load_canonical_rows_jsonl(path)


def test_duckdb_loader_reads_every_row_not_bounded_query_default(tmp_path: Path):
    database_path = tmp_path / "rows.duckdb"
    source = make_source_row(CellValueStatus.FORMULA_WITH_CACHED_VALUE.value)
    rows = tuple(replace(source, row_id=f"row-{index:04d}") for index in range(1_001))
    with DuckDBStore(database_path) as store:
        store.write_rows(rows)
    original = database_path.read_bytes()

    restored = load_canonical_rows_duckdb(database_path)

    assert len(restored) == 1_001
    assert restored[0].row_id == "row-0000"
    assert restored[-1].row_id == "row-1000"
    assert database_path.read_bytes() == original


def test_duckdb_loader_rejects_empty_database_without_modifying_it(tmp_path: Path):
    database_path = tmp_path / "empty.duckdb"
    database_path.write_bytes(b"")
    original = database_path.read_bytes()

    with pytest.raises(StorageError):
        load_canonical_rows_duckdb(database_path)

    assert database_path.read_bytes() == original


def test_duckdb_loader_rejects_foreign_database_without_modifying_it(tmp_path: Path):
    database_path = tmp_path / "foreign.duckdb"
    connection = duckdb.connect(str(database_path))
    try:
        connection.execute("CREATE TABLE foreign_rows (id INTEGER)")
    finally:
        connection.close()
    original = database_path.read_bytes()

    with pytest.raises(StorageSchemaError, match="schema_version"):
        load_canonical_rows_duckdb(database_path)

    assert database_path.read_bytes() == original


@pytest.mark.parametrize(
    ("path", "requested", "expected"),
    [
        ("rows.duckdb", "auto", "duckdb"),
        ("rows.JSONL", "auto", "jsonl"),
        ("rows.data", "duckdb", "duckdb"),
    ],
)
def test_resolves_input_format(path: str, requested: str, expected: str):
    assert resolve_input_format(Path(path), requested) == expected


def test_unknown_input_extension_requires_explicit_format():
    with pytest.raises(ValueError, match="Не удалось определить"):
        resolve_input_format(Path("rows.data"))
