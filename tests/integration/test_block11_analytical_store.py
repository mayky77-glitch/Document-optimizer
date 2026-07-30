from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from report_processor.analytics import (
    ANALYTICAL_MAX_QUERY_LIMIT,
    AnalyticalQuery,
    AnalyticalQueryError,
    AnalyticalStore,
    AnalyticalWriteError,
)
from tests.fixtures.analytics.builders import rule_set, source_row, target_row

from report_processor.storage import DuckDBStore


def test_analytical_store_is_separate_from_existing_storage_v1(tmp_path: Path):
    primary_path = tmp_path / "primary.duckdb"
    analytical_path = tmp_path / "analytics.duckdb"
    with DuckDBStore(primary_path) as primary:
        assert primary.write_rows(()).row_count == 0
    with AnalyticalStore(analytical_path) as analytical:
        analytical.load_source_rows((source_row(),))

    assert primary_path != analytical_path
    with DuckDBStore(primary_path) as primary:
        assert list(primary.iter_rows()) == []


def test_source_load_keys_by_source_row_id_not_line_id_and_preserves_legitimate_collisions(
    tmp_path: Path,
):
    with AnalyticalStore(tmp_path / "analytics.duckdb") as store:
        result = store.load_source_rows(
            (
                source_row("source-a:0002", line_id="same"),
                source_row("source-a:0001", line_id="same"),
            )
        )
        rows = store.query(AnalyticalQuery(name="source_rows", limit=10))

    assert (result.received_count, result.inserted_count, result.unchanged_count) == (2, 2, 0)
    assert [row.source_row_id for row in rows] == ["source-a:0001", "source-a:0002"]


def test_target_load_requires_identity_and_stable_sha256_id(tmp_path: Path):
    with AnalyticalStore(tmp_path / "analytics.duckdb") as store:
        target = target_row(target_row_id="")
        result = store.load_target_rows((target,))
        rows = store.query(AnalyticalQuery(name="target_rows", limit=10))

    assert result.inserted_count == 1
    assert rows[0].target_row_id == target.deterministic_id()
    assert len(rows[0].target_row_id) == 64


def test_rule_sets_are_keyed_by_content_hash_and_clauses_are_flattened(tmp_path: Path):
    rules = rule_set(clauses=(("quantity", "greater_than", "0"), ("unit", "equals", "m")))
    with AnalyticalStore(tmp_path / "analytics.duckdb") as store:
        result = store.load_rule_set(rules)
        rows = store.query(AnalyticalQuery(name="rules", limit=10))

    assert result.inserted_count == 1
    assert rows[0].content_hash == rules.content_hash
    assert rows[0].clauses == (("quantity", "greater_than", "0"), ("unit", "equals", "m"))


@pytest.mark.parametrize(
    ("loader", "payload"),
    [("load_source_rows", source_row()), ("load_target_rows", target_row())],
)
def test_identical_duplicate_records_are_unchanged(tmp_path: Path, loader: str, payload: object):
    with AnalyticalStore(tmp_path / "analytics.duckdb") as store:
        load = getattr(store, loader)
        first = load((payload,))
        duplicate = load((payload,))

    assert (first.inserted_count, duplicate.inserted_count, duplicate.unchanged_count) == (1, 0, 1)


def test_conflicting_same_source_id_rolls_back_entire_batch(tmp_path: Path):
    original = source_row("source-a:original")
    conflicting = source_row("source-a:conflict")
    with AnalyticalStore(tmp_path / "analytics.duckdb") as store:
        store.load_source_rows((original,))
        with pytest.raises(AnalyticalWriteError, match=r"source_row_id|duplicate|повтор"):
            store.load_source_rows(
                (source_row("source-a:new"), conflicting, replace(conflicting, status="ERROR"))
            )
        rows = store.query(AnalyticalQuery(name="source_rows", limit=10))

    assert [row.source_row_id for row in rows] == ["source-a:original"]


def test_query_order_and_diagnostic_jsonl_export_are_deterministic_and_atomic(tmp_path: Path):
    output_path = tmp_path / "diagnostics.jsonl"
    with AnalyticalStore(tmp_path / "analytics.duckdb") as store:
        store.load_source_rows(
            (source_row("source-a:c"), source_row("source-a:a"), source_row("source-a:b"))
        )
        first_rows = store.query(AnalyticalQuery(name="source_rows", limit=10))
        first = store.export_diagnostics_jsonl(output_path)
        second = store.export_diagnostics_jsonl(output_path)

    payload = output_path.read_bytes()
    assert [row.source_row_id for row in first_rows] == ["source-a:a", "source-a:b", "source-a:c"]
    assert first.sha256 == second.sha256 == hashlib.sha256(payload).hexdigest()
    assert first.bytes_written == len(payload)
    assert output_path.read_bytes() == payload
    assert [json.loads(line)["source_row_id"] for line in payload.splitlines()] == [
        "source-a:a",
        "source-a:b",
        "source-a:c",
    ]


@pytest.mark.parametrize("limit", [0, ANALYTICAL_MAX_QUERY_LIMIT + 1, None])
def test_named_queries_are_allowlisted_and_limits_are_bounded(tmp_path: Path, limit: int | None):
    with AnalyticalStore(tmp_path / "analytics.duckdb") as store:
        with pytest.raises(AnalyticalQueryError, match="limit"):
            store.query(AnalyticalQuery(name="source_rows", limit=limit))
        with pytest.raises(AnalyticalQueryError, match=r"allow|name|query"):
            store.query(
                AnalyticalQuery(name="source_rows; DROP TABLE analytical_source_rows", limit=1)
            )


def test_equality_filters_are_bound_values_and_injection_payload_is_inert(tmp_path: Path):
    injection = "source-a' OR 1=1 --"
    with AnalyticalStore(tmp_path / "analytics.duckdb") as store:
        store.load_source_rows(
            (source_row("source-a:1"), source_row("source-b:1", line_id="other"))
        )
        rows = store.query(
            AnalyticalQuery(name="source_rows", filters={"source_file_id": injection}, limit=10)
        )
        remaining = store.query(AnalyticalQuery(name="source_rows", limit=10))

    assert rows == ()
    assert [row.source_row_id for row in remaining] == ["source-a:1", "source-b:1"]


def test_exact_decimal_38_18_survives_store_and_query_without_rounding(tmp_path: Path):
    exact = Decimal("12345678901234567890.123456789012345678")
    with AnalyticalStore(tmp_path / "analytics.duckdb") as store:
        store.load_source_rows((source_row(quantity=exact),))
        rows = store.query(AnalyticalQuery(name="source_rows", limit=10))

    assert rows[0].contract_quantity == exact
