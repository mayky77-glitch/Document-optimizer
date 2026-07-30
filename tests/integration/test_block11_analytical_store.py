from __future__ import annotations

import hashlib
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from report_processor.analytics import (
    AnalyticalQuery,
    AnalyticalQueryError,
    AnalyticalStore,
    AnalyticalWriteError,
)
from tests.fixtures.analytics.builders import (
    normalized_source_row,
    target_report_row,
    validated_rule_set,
)

from report_processor.storage import DuckDBStore


def test_analytics_database_is_isolated_from_storage_v1(tmp_path: Path):
    primary, analytical = tmp_path / "primary.duckdb", tmp_path / "analytics.duckdb"
    with DuckDBStore(primary) as primary_store:
        primary_store.write_rows(())
    with AnalyticalStore(analytical) as store:
        store.load_source_rows((normalized_source_row(),))
    with DuckDBStore(primary) as primary_store:
        assert list(primary_store.iter_rows()) == []


def test_source_rows_key_by_source_row_id_while_same_line_id_survives(tmp_path: Path):
    first, second = normalized_source_row("source-a:1"), normalized_source_row("source-b:2")
    second = replace(second, line_id=first.line_id)
    with AnalyticalStore(tmp_path / "analytics.duckdb") as store:
        result = store.load_source_rows((second, first))
        rows = store.query(AnalyticalQuery("source_rows", limit=10)).rows
    assert (result.received_count, result.inserted_count) == (2, 2)
    assert [row["source_row_id"] for row in rows] == ["source-a:1", "source-b:2"]


def test_target_identity_is_sha256_of_explicit_source_context(tmp_path: Path):
    source_id, fingerprint = "target-a", "a" * 64
    target = target_report_row()
    with AnalyticalStore(tmp_path / "analytics.duckdb") as store:
        store.load_target_rows(
            (target,), target_source_id=source_id, target_fingerprint=fingerprint
        )
        row = store.query(AnalyticalQuery("target_rows", limit=10)).rows[0]
    expected = hashlib.sha256(
        f"{source_id}{fingerprint}{target.sheet_name}{target.row_number}".encode()
    ).hexdigest()
    assert row["target_row_id"] == expected


def test_rule_set_uses_content_hash_and_flattens_real_block10_clauses(tmp_path: Path):
    rules = validated_rule_set()
    with AnalyticalStore(tmp_path / "analytics.duckdb") as store:
        first, duplicate = store.load_rule_set(rules), store.load_rule_set(rules)
        clauses = store.query(AnalyticalQuery("rule_clauses", limit=10)).rows
    assert (first.inserted_count, duplicate.unchanged_count) == (1, 1)
    assert clauses[0]["content_hash"] == rules.content_hash
    assert {"rule_id", "clause_index", "action", "literal"} <= set(clauses[0])


def test_conflicting_same_source_identifier_rolls_back_full_batch(tmp_path: Path):
    original, conflicting = normalized_source_row("source-a:1"), normalized_source_row("source-a:2")
    with AnalyticalStore(tmp_path / "analytics.duckdb") as store:
        store.load_source_rows((original,))
        with pytest.raises(AnalyticalWriteError, match=r"Повторный|payload"):
            store.load_source_rows(
                (
                    normalized_source_row("source-a:new"),
                    conflicting,
                    replace(conflicting, line_id="changed"),
                )
            )
        rows = store.query(AnalyticalQuery("source_rows", limit=10)).rows
    assert [row["source_row_id"] for row in rows] == ["source-a:1"]


def test_named_queries_filters_injection_deterministic_order_and_diagnostics_export(tmp_path: Path):
    output = tmp_path / "diagnostics.jsonl"
    with AnalyticalStore(tmp_path / "analytics.duckdb") as store:
        store.load_source_rows(
            (normalized_source_row("source-a:c"), normalized_source_row("source-a:a"))
        )
        ordered = store.query(AnalyticalQuery("source_rows", limit=10)).rows
        injected = store.query(
            AnalyticalQuery("source_rows", {"source_file_id": "x' OR 1=1 --"}, 10)
        ).rows
        first, second = (
            store.export_diagnostics_jsonl(output),
            store.export_diagnostics_jsonl(output),
        )
    assert [row["source_row_id"] for row in ordered] == ["source-a:a", "source-a:c"]
    assert injected == ()
    assert (first.row_count, first.bytes_written) == (2, len(output.read_bytes()))
    assert (
        output.read_bytes() == output.read_bytes() and first.bytes_written == second.bytes_written
    )


@pytest.mark.parametrize(
    "query", [AnalyticalQuery("unknown", limit=1), AnalyticalQuery("source_rows", limit=10_001)]
)
def test_named_query_allowlist_and_limit_are_bounded(tmp_path: Path, query: AnalyticalQuery):
    with (
        AnalyticalStore(tmp_path / "analytics.duckdb") as store,
        pytest.raises(AnalyticalQueryError),
    ):
        store.query(query)


def test_decimal_exact_value_survives_without_rounding(tmp_path: Path):
    exact = Decimal("12345678901234567890.123456789012345678")
    with AnalyticalStore(tmp_path / "analytics.duckdb") as store:
        store.load_source_rows((normalized_source_row(quantity=exact),))
        row = store.query(AnalyticalQuery("source_rows", limit=1)).rows[0]
    assert row["contract_quantity"] == exact
