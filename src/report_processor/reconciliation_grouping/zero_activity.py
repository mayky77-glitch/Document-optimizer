"""Ephemeral zero-activity filtering for reconciliation review views."""

from __future__ import annotations

from collections.abc import Iterable

from report_processor.reconciliation_review.models import ReviewRow

from .models import RowPartition, finite_decimal_zero


def is_zero_activity(row: ReviewRow) -> bool:
    """Hide only rows with two finite Decimal values exactly equal to zero."""
    return finite_decimal_zero(row.quantity) and finite_decimal_zero(row.cost)


def partition_rows(rows: Iterable[ReviewRow]) -> RowPartition:
    """Keep all source rows internally while exposing a fresh visible/hidden split."""
    source_rows = tuple(rows)
    visible_rows = tuple(row for row in source_rows if not is_zero_activity(row))
    hidden_rows = tuple(row for row in source_rows if is_zero_activity(row))
    return RowPartition(
        source_rows=source_rows,
        visible_rows=visible_rows,
        hidden_rows=hidden_rows,
    )
