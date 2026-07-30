from __future__ import annotations

from pathlib import Path

import duckdb
import pytest
from report_processor.analytics import ANALYTICAL_SCHEMA_VERSION, AnalyticalError, AnalyticalStore


def test_schema_has_exact_tables_columns_primary_keys_indexes_and_reporting_views(tmp_path: Path):
    path = tmp_path / "analytics.duckdb"
    with AnalyticalStore(path):
        pass
    connection = duckdb.connect(str(path), read_only=True)
    try:
        tables = {
            item[0]
            for item in connection.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
        }
        views = {
            item[0]
            for item in connection.execute(
                "SELECT view_name FROM duckdb_views() WHERE schema_name = 'main' AND NOT internal"
            ).fetchall()
        }
        indexes = {
            item[0]
            for item in connection.execute(
                "SELECT index_name FROM duckdb_indexes() WHERE schema_name = 'main'"
            ).fetchall()
        }
        version = connection.execute(
            "SELECT metadata_value FROM analytical_metadata WHERE metadata_key = 'schema_version'"
        ).fetchone()
        source_columns = {
            row[0]
            for row in connection.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'source_rows'"
            ).fetchall()
        }
        target_columns = {
            row[0]
            for row in connection.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'target_rows'"
            ).fetchall()
        }
        primary_keys = {
            row[0]: tuple(row[1])
            for row in connection.execute(
                "SELECT table_name, constraint_column_names FROM duckdb_constraints() "
                "WHERE constraint_type = 'PRIMARY KEY'"
            ).fetchall()
        }
    finally:
        connection.close()
    assert {
        "analytical_metadata",
        "source_rows",
        "target_rows",
        "rule_sets",
        "rule_clauses",
        "warnings",
    } <= tables
    assert {"v_source_rows", "v_target_rows", "v_rule_clauses", "v_diagnostics"} == views
    assert {"source_rows_line_id", "target_rows_source_fingerprint", "warnings_entity"} <= indexes
    assert version == (ANALYTICAL_SCHEMA_VERSION,)
    assert {
        "source_row_id",
        "line_id",
        "payload_hash",
        "contract_quantity",
        "payload_json",
    } <= source_columns
    assert {
        "target_row_id",
        "target_source_id",
        "target_fingerprint",
        "payload_json",
    } <= target_columns
    assert primary_keys["source_rows"] == ("source_row_id",)
    assert primary_keys["target_rows"] == ("target_row_id",)
    assert primary_keys["rule_sets"] == ("content_hash",)


def test_reporting_views_do_not_perform_block12_matching(tmp_path: Path):
    path = tmp_path / "analytics.duckdb"
    with AnalyticalStore(path):
        pass
    connection = duckdb.connect(str(path), read_only=True)
    try:
        sql = " ".join(
            row[0]
            for row in connection.execute(
                "SELECT sql FROM duckdb_views() WHERE schema_name = 'main' AND NOT internal"
            ).fetchall()
        ).casefold()
    finally:
        connection.close()
    assert "match" not in sql and " join " not in sql


@pytest.mark.parametrize("version", ["AnalyticalSchema-0", "AnalyticalSchema-2"])
def test_older_and_newer_versions_are_rejected(tmp_path: Path, version: str):
    path = tmp_path / "analytics.duckdb"
    with AnalyticalStore(path):
        pass
    connection = duckdb.connect(str(path))
    try:
        connection.execute(
            "UPDATE analytical_metadata SET metadata_value = ? "
            "WHERE metadata_key = 'schema_version'",
            [version],
        )
    finally:
        connection.close()
    with pytest.raises(AnalyticalError, match=r"схем|schema|Версия"):
        AnalyticalStore(path)


def test_corrupt_and_partial_database_are_controlled(tmp_path: Path):
    corrupt = tmp_path / "corrupt.duckdb"
    corrupt.write_text("not duckdb", encoding="utf-8")
    with pytest.raises(AnalyticalError):
        AnalyticalStore(corrupt)
    partial = tmp_path / "partial.duckdb"
    duckdb.connect(str(partial)).execute("CREATE TABLE source_rows (source_row_id VARCHAR)")
    with pytest.raises(AnalyticalError):
        AnalyticalStore(partial)
