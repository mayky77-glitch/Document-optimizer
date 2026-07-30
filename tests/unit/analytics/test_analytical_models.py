from __future__ import annotations

from decimal import Decimal

import pytest

from fixtures.analytics.builders import normalized_source_row, target_report_row
from report_processor.analytics import AnalyticalQuery, AnalyticalStore, AnalyticalWriteError


def test_real_block8_and_9_rows_keep_provenance_classification_status_warnings(tmp_path):
    source = normalized_source_row()
    target = target_report_row()
    with AnalyticalStore(tmp_path / "analytics.duckdb") as store:
        store.load_source_rows((source,))
        store.load_target_rows((target,), target_source_id="target-a", target_fingerprint="a" * 64)
        source_result = store.query(AnalyticalQuery("source_rows", limit=10))
        target_result = store.query(AnalyticalQuery("target_rows", limit=10))

    assert source_result.rows[0]["source_file_id"] == "source-a"
    assert source_result.rows[0]["line_id"] == source.line_id
    assert target_result.rows[0]["status"] == "WARNING"
    assert target_result.rows[0]["target_fingerprint"] == "a" * 64


@pytest.mark.parametrize("quantity", [Decimal("1.0000000000000000001"), Decimal("1e20")])
def test_decimal_38_18_rejects_scale_and_precision_without_rounding(tmp_path, quantity):
    with (
        AnalyticalStore(tmp_path / "analytics.duckdb") as store,
        pytest.raises(AnalyticalWriteError, match=r"scale|precision"),
    ):
        store.load_source_rows((normalized_source_row(quantity=quantity),))


def test_decimal_float_is_rejected_without_coercion(tmp_path):
    row = normalized_source_row()
    object.__setattr__(row.source_row, "contract_quantity", 1.25)
    with (
        AnalyticalStore(tmp_path / "analytics.duckdb") as store,
        pytest.raises(AnalyticalWriteError, match="float"),
    ):
        store.load_source_rows((row,))


@pytest.mark.parametrize("source_id,fingerprint", [("", "a" * 64), ("target-a", "")])
def test_target_load_requires_explicit_nonempty_source_context(tmp_path, source_id, fingerprint):
    with (
        AnalyticalStore(tmp_path / "analytics.duckdb") as store,
        pytest.raises(AnalyticalWriteError),
    ):
        store.load_target_rows(
            (target_report_row(),), target_source_id=source_id, target_fingerprint=fingerprint
        )
