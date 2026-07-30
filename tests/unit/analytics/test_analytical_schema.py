from __future__ import annotations

from pathlib import Path

import duckdb
import pytest
from report_processor.analytics import (
    ANALYTICAL_SCHEMA_VERSION,
    AnalyticalSchemaError,
    AnalyticalStore,
)


def _table_columns(connection: duckdb.DuckDBPyConnection, table: str) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ?", [table]
        ).fetchall()
    }


def test_schema_has_separate_analytical_database_and_required_tables_columns_indexes_and_views(
    tmp_path: Path,
):
    database_path = tmp_path / "analytics.duckdb"
    with AnalyticalStore(database_path):
        pass

    connection = duckdb.connect(str(database_path), read_only=True)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
        }
        views = {
            row[0]
            for row in connection.execute(
                "SELECT table_name FROM information_schema.views WHERE table_schema = 'main'"
            ).fetchall()
        }
        indexes = {
            row[0]
            for row in connection.execute("SELECT index_name FROM duckdb_indexes()").fetchall()
        }

        assert {
            "analytical_metadata",
            "analytical_source_rows",
            "analytical_target_rows",
            "analytical_rules",
        } <= tables
        assert {
            "analytical_source_rows_view",
            "analytical_target_rows_view",
            "analytical_rules_view",
        } <= views
        assert {
            "idx_analytical_source_rows_source_row_id",
            "idx_analytical_target_rows_source_id",
        } <= indexes
        assert {"source_row_id", "line_id", "payload_json", "content_hash"} <= _table_columns(
            connection, "analytical_source_rows"
        )
        assert {
            "target_row_id",
            "target_source_id",
            "target_source_fingerprint",
            "payload_json",
        } <= _table_columns(connection, "analytical_target_rows")
        assert {"content_hash", "clauses_json", "payload_json"} <= _table_columns(
            connection, "analytical_rules"
        )
        assert connection.execute(
            "SELECT metadata_value FROM analytical_metadata WHERE metadata_key = 'schema_version'"
        ).fetchone() == (str(ANALYTICAL_SCHEMA_VERSION),)
    finally:
        connection.close()


def test_views_are_reporting_only_and_do_not_perform_block12_matching(tmp_path: Path):
    database_path = tmp_path / "analytics.duckdb"
    with AnalyticalStore(database_path):
        pass

    connection = duckdb.connect(str(database_path), read_only=True)
    try:
        definitions = "\n".join(
            row[0]
            for row in connection.execute(
                "SELECT sql FROM duckdb_views() WHERE view_name LIKE 'analytical_%_view'"
            ).fetchall()
        ).casefold()
    finally:
        connection.close()

    assert "match" not in definitions
    assert "join analytical_source_rows" not in definitions
    assert "join analytical_target_rows" not in definitions


@pytest.mark.parametrize("version", ["0", str(ANALYTICAL_SCHEMA_VERSION + 1)])
def test_older_and_newer_schema_versions_are_rejected_controlled(tmp_path: Path, version: str):
    database_path = tmp_path / f"schema-{version}.duckdb"
    with AnalyticalStore(database_path):
        pass
    connection = duckdb.connect(str(database_path))
    try:
        connection.execute(
            "UPDATE analytical_metadata SET metadata_value = ? "
            "WHERE metadata_key = 'schema_version'",
            [version],
        )
    finally:
        connection.close()

    with pytest.raises(AnalyticalSchemaError, match=r"schema|схем"):
        AnalyticalStore(database_path)


def test_corrupt_and_partial_analytical_database_are_controlled_without_stamping(tmp_path: Path):
    corrupt_path = tmp_path / "corrupt.duckdb"
    corrupt_path.write_text("not a database", encoding="utf-8")
    with pytest.raises(AnalyticalSchemaError):
        AnalyticalStore(corrupt_path)

    partial_path = tmp_path / "partial.duckdb"
    connection = duckdb.connect(str(partial_path))
    try:
        connection.execute("CREATE TABLE analytical_source_rows (source_row_id VARCHAR)")
    finally:
        connection.close()
    with pytest.raises(AnalyticalSchemaError, match=r"schema_version|metadata"):
        AnalyticalStore(partial_path)
