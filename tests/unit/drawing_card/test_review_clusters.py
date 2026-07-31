"""Regression contract for deterministic, reversible review clusters."""

from __future__ import annotations

from decimal import Decimal

from report_processor.drawing_card.models import (
    DrawingSourceLocation,
    DrawingSourceRow,
    MatchDecision,
    TargetWorkCategory,
)
from report_processor.drawing_card.review.clusters import build_review_clusters, cluster_approvals
from report_processor.drawing_card.statuses import Status


def _row(row_id: str, *, unit: str = "м", formula: bool = False) -> DrawingSourceRow:
    return DrawingSourceRow(
        row_id=row_id,
        location=DrawingSourceLocation("source", "private.xlsx", "Лист1", 10, ("A10",)),
        object_index_raw="1006",
        drawing_code_raw="А-001",
        work_name_raw="Монтаж контрольного кабеля",
        unit_raw=unit,
        remaining_quantity=Decimal("12"),
        remaining_total_cost=Decimal("3500"),
        formula_values=("=SUM(A1:A2)",) if formula else (),
        cached_values=(None,) if formula else (),
        source_document_type="ks6a",
        source_period="2026-07",
        source_revision=None,
        status=Status.WARNING if formula else Status.OK,
        warnings=(Status.FORMULA_WITHOUT_CACHED_VALUE,) if formula else (),
    )


def _decision(row_id: str, *, warning: str | None = None) -> MatchDecision:
    return MatchDecision(
        row_id=row_id,
        category=TargetWorkCategory.LOW_CURRENT_CABLE,
        quantity_decision="review",
        cost_decision="review",
        quantity_rule_id=None,
        cost_rule_id=None,
        quantity_confidence=0.72,
        cost_confidence=0.72,
        matching_strategy="manual_review",
        evidence_ids=(),
        reason="Manual review",
        requires_manual_review=True,
        status=Status.WARNING if warning else Status.OK,
        warnings=(warning,) if warning else (),
    )


def test_clusters_merge_only_compatible_rows_and_keep_cross_unit_rows_separate() -> None:
    rows = {row.row_id: row for row in (_row("a"), _row("b"), _row("c", unit="шт"))}
    decisions = {row_id: _decision(row_id) for row_id in rows}

    clusters = build_review_clusters(rows, decisions)

    assert {cluster.member_ids for cluster in clusters} == {("a", "b"), ("c",)}
    assert sum(len(cluster.member_ids) for cluster in clusters) == 3


def test_formula_hazard_isolated_from_an_otherwise_identical_safe_cluster() -> None:
    rows = {"safe": _row("safe"), "formula": _row("formula", formula=True)}
    decisions = {
        "safe": _decision("safe"),
        "formula": _decision("formula", warning=Status.FORMULA_WITHOUT_CACHED_VALUE),
    }

    clusters = build_review_clusters(rows, decisions)

    assert len(clusters) == 2
    assert {cluster.has_hazard for cluster in clusters} == {False, True}
    assert {cluster.reason_code for cluster in clusters} == {
        "manual_review",
        "formula_or_excel_error",
    }


def test_cluster_fanout_validates_once_and_covers_every_member() -> None:
    cluster = build_review_clusters(
        {"a": _row("a"), "b": _row("b")},
        {"a": _decision("a"), "b": _decision("b")},
    )[0]

    approvals = cluster_approvals(cluster, "change_category", "concrete_works")

    assert set(approvals) == {"a", "b"}
    assert {approval.action for approval in approvals.values()} == {"change_category"}
    assert {approval.category for approval in approvals.values()} == {
        TargetWorkCategory.CONCRETE_WORKS
    }
