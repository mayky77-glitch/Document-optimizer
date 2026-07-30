from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime, time
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
from report_processor.extraction.serialization import _to_json_compatible
from report_processor.storage import (
    SCHEMA_VERSION,
    DuckDBStore,
    StorageError,
    StorageQuery,
    StorageSchemaError,
    StorageWriteError,
)


def _row(
    row_id: str,
    *,
    source_file_id: str = "file-1",
    document_index: str | None = "1006 (682)",
    document_period: str | None = "2026-07",
    source_type: str = "ks2",
    work_name: str = "Монтаж",
    with_provenance: bool = False,
) -> CanonicalSourceRow:
    location = SourceLocation(source_file_id, "report.xlsx", "КС-2", source_type, 4)
    source_values = ()
    if with_provenance:
        source_values = (
            ExtractedCellValue(
                logical_column="work_name",
                coordinate="B4",
                raw_formula_value="=A1",
                raw_cached_value="Монтаж",
                effective_value="Монтаж",
                effective_value_source="cached_value",
                formula_data_type="f",
                cached_data_type="s",
                is_formula=True,
                is_empty=False,
                is_error=False,
                status="OK",
                warnings=("FORMULA",),
                provenance=ValueProvenance(
                    location=SourceLocation(
                        source_file_id,
                        "report.xlsx",
                        "КС-2",
                        source_type,
                        4,
                        2,
                        "B",
                        "B4",
                    ),
                    logical_column="work_name",
                    header_text="Наименование",
                    formula="=A1",
                    cached_value_available=True,
                    value_source="cached_value",
                    warnings=("FORMULA",),
                ),
            ),
        )
    return CanonicalSourceRow(
        row_id=row_id,
        source_type=source_type,
        source_location=location,
        document_index=document_index,
        document_period=document_period,
        object_code_raw="1006",
        object_name_raw="Объект",
        subobject_code_raw=None,
        subobject_name_raw=None,
        position_code_raw="0004",
        work_name_raw=work_name,
        unit_raw="м",
        contract_quantity=Decimal("123.450000000000000001"),
        current_period_quantity=Decimal("12.3"),
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
        source_values=source_values,
        status="OK",
        warnings=("ROW_WARNING",),
    )


def test_creates_idempotent_initial_schema_and_metadata(tmp_path: Path):
    database_path = tmp_path / "nested" / "rows.duckdb"
    with DuckDBStore(database_path) as store:
        assert store.write_rows(()).row_count == 0

    connection = duckdb.connect(str(database_path), read_only=True)
    try:
        assert connection.execute(
            "SELECT metadata_value FROM storage_metadata WHERE metadata_key = 'schema_version'"
        ).fetchone() == (str(SCHEMA_VERSION),)
        assert connection.execute("SELECT COUNT(*) FROM canonical_rows").fetchone() == (0,)
    finally:
        connection.close()

    with DuckDBStore(database_path) as reopened:
        assert list(reopened.iter_rows()) == []


def test_identical_row_is_idempotent_and_changed_row_updates(tmp_path: Path):
    database_path = tmp_path / "rows.duckdb"
    row = _row("row-1")
    with DuckDBStore(database_path) as store:
        first = store.write_rows((row,))
        same = store.write_rows((row,))
        changed = store.write_rows((replace(row, work_name_raw="Изменённый монтаж"),))
        stored = store.get_row("row-1")

    assert (first.inserted_count, first.updated_count, first.unchanged_count) == (1, 0, 0)
    assert (same.inserted_count, same.updated_count, same.unchanged_count) == (0, 0, 1)
    assert (changed.inserted_count, changed.updated_count, changed.unchanged_count) == (0, 1, 0)
    assert stored is not None
    assert stored.work_name_raw == "Изменённый монтаж"


@pytest.mark.parametrize(
    ("first_work", "second_work"),
    [("Первая версия", "Вторая версия"), ("Вторая версия", "Первая версия")],
)
def test_conflicting_duplicate_row_ids_fail_before_transaction(
    tmp_path: Path,
    first_work: str,
    second_work: str,
):
    database_path = tmp_path / "rows.duckdb"
    original = _row("duplicate", work_name="Сохранённая версия")
    with DuckDBStore(database_path) as store:
        store.write_rows((original,))
        with pytest.raises(StorageWriteError, match="повторный row_id"):
            store.write_rows(
                (
                    replace(original, work_name_raw=first_work),
                    replace(original, work_name_raw=second_work),
                )
            )
        assert store.get_row("duplicate") == original


def test_identical_duplicate_row_ids_have_explicit_received_count(tmp_path: Path):
    row = _row("duplicate")
    with DuckDBStore(tmp_path / "rows.duckdb") as store:
        first = store.write_rows((row, row))
        second = store.write_rows((row, row))

    first_counts = (
        first.received_count,
        first.inserted_count,
        first.updated_count,
        first.unchanged_count,
    )
    assert first_counts == (
        2,
        1,
        0,
        1,
    )
    second_counts = (
        second.received_count,
        second.inserted_count,
        second.updated_count,
        second.unchanged_count,
    )
    assert second_counts == (
        2,
        0,
        0,
        2,
    )


def test_failed_batch_rolls_back_prior_batch_contents(tmp_path: Path):
    database_path = tmp_path / "rows.duckdb"
    original = _row("original")
    broken_location = SourceLocation(None, "report.xlsx", "КС-2", "ks2", 4)  # type: ignore[arg-type]
    broken = replace(_row("broken"), source_location=broken_location)
    with DuckDBStore(database_path) as store:
        store.write_rows((original,))
        with pytest.raises(StorageWriteError):
            store.write_rows((_row("new"), broken))
        assert [row.row_id for row in store.iter_rows()] == ["original"]


def test_provenance_round_trip_and_jsonl_export_match_existing_shape(tmp_path: Path):
    database_path = tmp_path / "rows.duckdb"
    row = _row("provenance", with_provenance=True)
    output_path = tmp_path / "rows.jsonl"
    with DuckDBStore(database_path) as store:
        store.write_rows((row,))
        restored = store.get_row(row.row_id)
        exported = store.export_jsonl(output_path)

    assert restored == row
    assert exported.row_count == 1
    assert json.loads(output_path.read_text(encoding="utf-8")) == _to_json_compatible(row)
    assert json.loads(exported.meta_path.read_text(encoding="utf-8"))["total_rows"] == 1


def test_temporal_provenance_round_trips_and_exports_as_established_iso_strings(tmp_path: Path):
    row = _row("temporal", with_provenance=True)
    cell = row.source_values[0]
    temporal_cell = replace(
        cell,
        raw_formula_value=date(2026, 7, 30),
        raw_cached_value=datetime(2026, 7, 30, 12, 34, 56, tzinfo=UTC),
        effective_value=time(12, 34, 56, 123456),
    )
    row = replace(row, source_values=(temporal_cell,))
    output_path = tmp_path / "rows.jsonl"
    with DuckDBStore(tmp_path / "rows.duckdb") as store:
        store.write_rows((row,))
        restored = store.get_row(row.row_id)
        store.export_jsonl(output_path)

    assert restored == row
    exported = json.loads(output_path.read_text(encoding="utf-8"))["source_values"][0]
    assert exported["raw_formula_value"] == "2026-07-30"
    assert exported["raw_cached_value"] == "2026-07-30T12:34:56+00:00"
    assert exported["effective_value"] == "12:34:56.123456"


def test_filters_and_order_are_deterministic_and_bounded(tmp_path: Path):
    database_path = tmp_path / "rows.duckdb"
    with DuckDBStore(database_path) as store:
        store.write_rows(
            (
                _row("row-c"),
                _row("row-a"),
                _row("row-b", source_file_id="file-2", source_type="svvr"),
            )
        )
        filtered = list(store.iter_rows(StorageQuery(source_file_id="file-1", limit=10)))
        one = list(store.iter_rows(StorageQuery(limit=1)))

    assert [row.row_id for row in filtered] == ["row-a", "row-c"]
    assert [row.row_id for row in one] == ["row-a"]


def test_default_export_includes_more_than_iter_rows_default_limit(tmp_path: Path):
    output_path = tmp_path / "all.jsonl"
    rows = tuple(_row(f"row-{index:04d}") for index in range(1_001))
    with DuckDBStore(tmp_path / "rows.duckdb") as store:
        store.write_rows(rows)
        assert len(list(store.iter_rows())) == 1_000
        exported = store.export_jsonl(output_path)

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert exported.row_count == 1_001
    assert len(lines) == 1_001
    assert json.loads(lines[0])["row_id"] == "row-0000"
    assert json.loads(lines[-1])["row_id"] == "row-1000"
    assert json.loads(exported.meta_path.read_text(encoding="utf-8"))["total_rows"] == 1_001


def test_explicit_export_query_remains_filtered_and_bounded(tmp_path: Path):
    output_path = tmp_path / "filtered.jsonl"
    with DuckDBStore(tmp_path / "rows.duckdb") as store:
        store.write_rows(
            (
                _row("row-c", source_type="ks2"),
                _row("row-a", source_type="ks2"),
                _row("row-b", source_type="svvr"),
            )
        )
        exported = store.export_jsonl(output_path, StorageQuery(source_type="ks2", limit=1))

    assert exported.row_count == 1
    assert json.loads(output_path.read_text(encoding="utf-8"))["row_id"] == "row-a"
    assert json.loads(exported.meta_path.read_text(encoding="utf-8"))["total_rows"] == 1


def test_iterator_isolation_survives_interleaved_store_operations(tmp_path: Path):
    with DuckDBStore(tmp_path / "rows.duckdb") as store:
        store.write_rows((_row("row-a"), _row("row-b"), _row("row-c")))
        rows = store.iter_rows(StorageQuery(limit=10))
        assert next(rows).row_id == "row-a"
        assert store.get_row("row-c") is not None
        store.write_rows((_row("row-d"),))
        assert [row.row_id for row in rows] == ["row-b", "row-c"]
        assert [row.row_id for row in store.iter_rows(StorageQuery(limit=10))] == [
            "row-a",
            "row-b",
            "row-c",
            "row-d",
        ]


@pytest.mark.parametrize("limit", [0, 10_001, None])
def test_query_limit_is_controlled(tmp_path: Path, limit: int | None):
    with DuckDBStore(tmp_path / "rows.duckdb") as store, pytest.raises(StorageError, match="limit"):
        list(store.iter_rows(StorageQuery(limit=limit)))


def test_corrupt_database_and_newer_schema_are_controlled(tmp_path: Path):
    corrupt_path = tmp_path / "corrupt.duckdb"
    corrupt_path.write_text("not a duckdb database", encoding="utf-8")
    with pytest.raises(StorageError):
        DuckDBStore(corrupt_path)

    newer_path = tmp_path / "newer.duckdb"
    with DuckDBStore(newer_path):
        pass
    connection = duckdb.connect(str(newer_path))
    try:
        connection.execute(
            "UPDATE storage_metadata SET metadata_value = ? WHERE metadata_key = 'schema_version'",
            [str(SCHEMA_VERSION + 1)],
        )
    finally:
        connection.close()
    with pytest.raises(StorageSchemaError, match="новее"):
        DuckDBStore(newer_path)


def test_partial_table_without_metadata_is_rejected_without_stamping(tmp_path: Path):
    database_path = tmp_path / "partial.duckdb"
    connection = duckdb.connect(str(database_path))
    try:
        connection.execute("CREATE TABLE canonical_rows (row_id VARCHAR)")
    finally:
        connection.close()

    with pytest.raises(StorageSchemaError, match="schema_version"):
        DuckDBStore(database_path)

    connection = duckdb.connect(str(database_path), read_only=True)
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'storage_metadata'"
        ).fetchone() == (0,)
    finally:
        connection.close()


def test_name_complete_wrong_schema_is_rejected_at_open(tmp_path: Path):
    database_path = tmp_path / "wrong.duckdb"
    connection = duckdb.connect(str(database_path))
    try:
        columns = ", ".join(f"{name} VARCHAR" for name in _storage_columns())
        connection.execute(f"CREATE TABLE canonical_rows ({columns})")
        connection.execute(
            "CREATE TABLE storage_metadata (metadata_key VARCHAR PRIMARY KEY, "
            "metadata_value VARCHAR NOT NULL)"
        )
        connection.execute("INSERT INTO storage_metadata VALUES ('schema_version', '1')")
    finally:
        connection.close()

    with pytest.raises(StorageSchemaError, match="не соответствует"):
        DuckDBStore(database_path)


def test_missing_required_index_is_rejected_at_open(tmp_path: Path):
    database_path = tmp_path / "invalid-v1.duckdb"
    with DuckDBStore(database_path):
        pass
    connection = duckdb.connect(str(database_path))
    try:
        connection.execute("DROP INDEX canonical_rows_source_type")
    finally:
        connection.close()

    with pytest.raises(StorageSchemaError):
        DuckDBStore(database_path)


def test_missing_required_nullability_is_rejected_at_open(tmp_path: Path):
    database_path = tmp_path / "nullable-v1.duckdb"
    connection = duckdb.connect(str(database_path))
    try:
        columns = ", ".join(_storage_column_definition(name) for name in _storage_columns())
        connection.execute(f"CREATE TABLE canonical_rows ({columns})")
        for name, column in (
            ("canonical_rows_source_file_id", "source_file_id"),
            ("canonical_rows_document_index", "document_index"),
            ("canonical_rows_document_period", "document_period"),
            ("canonical_rows_source_type", "source_type"),
        ):
            connection.execute(f"CREATE INDEX {name} ON canonical_rows ({column})")
        connection.execute(
            "CREATE TABLE storage_metadata (metadata_key VARCHAR PRIMARY KEY, "
            "metadata_value VARCHAR NOT NULL)"
        )
        connection.execute("INSERT INTO storage_metadata VALUES ('schema_version', '1')")
    finally:
        connection.close()

    with pytest.raises(StorageSchemaError, match="nullability"):
        DuckDBStore(database_path)


def test_nullable_metadata_without_primary_key_is_rejected_before_version_read(tmp_path: Path):
    database_path = tmp_path / "lax-metadata.duckdb"
    with DuckDBStore(database_path):
        pass
    connection = duckdb.connect(str(database_path))
    try:
        _replace_metadata_table(
            connection,
            "metadata_key VARCHAR, metadata_value VARCHAR",
            (("schema_version", "1"),),
        )
    finally:
        connection.close()

    with pytest.raises(StorageSchemaError, match="storage_metadata"):
        DuckDBStore(database_path)


def test_duplicate_schema_version_rows_are_rejected_deterministically(tmp_path: Path):
    database_path = tmp_path / "duplicate-metadata.duckdb"
    with DuckDBStore(database_path):
        pass
    connection = duckdb.connect(str(database_path))
    try:
        _replace_metadata_table(
            connection,
            "metadata_key VARCHAR NOT NULL, metadata_value VARCHAR NOT NULL",
            (("schema_version", "1"), ("schema_version", "2")),
        )
    finally:
        connection.close()

    with pytest.raises(StorageSchemaError, match="storage_metadata"):
        DuckDBStore(database_path)


def test_metadata_with_unexpected_column_is_rejected_before_version_read(tmp_path: Path):
    database_path = tmp_path / "extra-metadata.duckdb"
    with DuckDBStore(database_path):
        pass
    connection = duckdb.connect(str(database_path))
    try:
        _replace_metadata_table(
            connection,
            "metadata_key VARCHAR PRIMARY KEY, metadata_value VARCHAR NOT NULL, note VARCHAR",
            (("schema_version", "1"),),
        )
    finally:
        connection.close()

    with pytest.raises(StorageSchemaError, match="лишние"):
        DuckDBStore(database_path)


def test_nonpristine_metadata_without_schema_version_is_rejected(tmp_path: Path):
    database_path = tmp_path / "missing-version.duckdb"
    with DuckDBStore(database_path):
        pass
    connection = duckdb.connect(str(database_path))
    try:
        _replace_metadata_table(
            connection,
            "metadata_key VARCHAR PRIMARY KEY, metadata_value VARCHAR NOT NULL",
            (),
        )
    finally:
        connection.close()

    with pytest.raises(StorageSchemaError, match="ровно одна"):
        DuckDBStore(database_path)


def _storage_columns() -> tuple[str, ...]:
    from report_processor.storage.duckdb_store import _ROW_COLUMNS

    return _ROW_COLUMNS


def _storage_column_definition(name: str) -> str:
    from report_processor.storage.duckdb_store import _COLUMN_SPEC

    data_type, nullable = next(
        (data_type, nullable) for key, data_type, nullable in _COLUMN_SPEC if key == name
    )
    if name == "row_id":
        return f"{name} {data_type} PRIMARY KEY"
    if name == "source_file_id":
        return f"{name} {data_type}"
    return f"{name} {data_type}" if nullable else f"{name} {data_type} NOT NULL"


def _replace_metadata_table(
    connection: duckdb.DuckDBPyConnection,
    definition: str,
    rows: tuple[tuple[str, str], ...],
) -> None:
    connection.execute("DROP TABLE storage_metadata")
    connection.execute(f"CREATE TABLE storage_metadata ({definition})")
    if rows:
        connection.executemany(
            "INSERT INTO storage_metadata (metadata_key, metadata_value) VALUES (?, ?)",
            rows,
        )
