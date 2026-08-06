"""Regression contract for deterministic, reversible review clusters."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from report_processor.drawing_card.models import (
    DrawingSourceLocation,
    DrawingSourceRow,
    MatchDecision,
    TargetWorkCategory,
)
from report_processor.drawing_card.review.clusters import (
    ReviewPacketContext,
    build_review_clusters,
    cluster_approvals,
)
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


def test_hazard_rows_are_always_singleton_even_with_identical_context() -> None:
    rows = {"first": _row("first", formula=True), "second": _row("second", formula=True)}
    decisions = {
        row_id: _decision(row_id, warning=Status.FORMULA_WITHOUT_CACHED_VALUE) for row_id in rows
    }

    clusters = build_review_clusters(rows, decisions)

    assert {cluster.member_ids for cluster in clusters} == {("first",), ("second",)}
    assert all(cluster.has_hazard and not cluster.packet_eligible for cluster in clusters)
    assert {cluster.controlled_difference_fields for cluster in clusters} == {("hazard",)}


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


def test_cable_coupling_groups_only_terminal_numbers_and_preserves_suffix() -> None:
    rows = {
        "one": _row("one"),
        "two": _row("two"),
        "other": _row("other"),
        "generic-one": _row("generic-one"),
        "generic-two": _row("generic-two"),
    }
    rows["one"] = replace(
        rows["one"], work_name_raw="Установка муфт соединительных кабельных 10 кВ (№1)"
    )
    rows["two"] = replace(
        rows["two"], work_name_raw="Установка муфт соединительных кабельных 10 кВ (№2)"
    )
    rows["other"] = replace(
        rows["other"], work_name_raw="Установка муфт соединительных кабельных 6 кВ (№3)"
    )
    rows["generic-one"] = replace(rows["generic-one"], work_name_raw="Монтаж коробки (№1)")
    rows["generic-two"] = replace(rows["generic-two"], work_name_raw="Монтаж коробки (№2)")

    clusters = build_review_clusters(rows, {row_id: _decision(row_id) for row_id in rows})

    assert {cluster.member_ids for cluster in clusters} == {
        ("one", "two"),
        ("other",),
        ("generic-one",),
        ("generic-two",),
    }
    assert next(cluster for cluster in clusters if cluster.member_ids == ("one", "two")).name == (
        "установка муфт соединительных кабельных 10 кв"
    )


def _context(
    *,
    normalized_work: str = "монтаж контрольного кабеля",
    source_type: str = "ks6a",
    review_reason: str = "manual_review",
    proposed_category: str = TargetWorkCategory.LOW_CURRENT_CABLE.value,
    match_mode: str = "manual_review",
    unit_compatibility_class: str = "same_unit",
    quantity_resolution_mode: str = "review",
    cost_resolution_mode: str = "review",
) -> ReviewPacketContext:
    return ReviewPacketContext(
        tenant_id="tenant-a",
        project_id="project-a",
        normalized_work=normalized_work,
        source_type=source_type,
        review_reason=review_reason,
        proposed_category=proposed_category,
        match_mode=match_mode,
        unit_compatibility_class=unit_compatibility_class,
        transactional_row_role="work_item",
        rules_version="rules-1",
        quantity_resolution_mode=quantity_resolution_mode,
        cost_resolution_mode=cost_resolution_mode,
    )


def test_strict_context_requires_exact_equality_for_each_packet_dimension() -> None:
    rows = {"a": _row("a"), "b": _row("b")}
    decisions = {row_id: _decision(row_id) for row_id in rows}
    baseline = _context()

    clusters = build_review_clusters(rows, decisions, contexts={"a": baseline, "b": baseline})

    assert [cluster.member_ids for cluster in clusters] == [("a", "b")]
    assert clusters[0].pivot_id == "a"
    assert clusters[0].packet_eligible
    assert clusters[0].match_mode == "manual_review"
    assert clusters[0].unit_compatibility_class == "same_unit"
    assert clusters[0].rules_version == "rules-1"

    for field, changed in {
        "tenant_id": "tenant-b",
        "project_id": "project-b",
        "normalized_work": "другая работа",
        "source_type": "ks2",
        "review_reason": "multiple_categories",
        "proposed_category": TargetWorkCategory.CONCRETE_WORKS.value,
        "match_mode": "dictionary",
        "unit_compatibility_class": "cost_only",
        "transactional_row_role": "aggregate",
        "rules_version": "rules-2",
        "quantity_resolution_mode": "approved",
        "cost_resolution_mode": "approved",
    }.items():
        contexts = {"a": baseline, "b": replace(baseline, **{field: changed})}
        separated = build_review_clusters(rows, decisions, contexts=contexts)
        assert {cluster.member_ids for cluster in separated} == {("a",), ("b",)}, field


def test_strict_context_missing_or_invalid_fails_closed_as_a_visible_singleton() -> None:
    rows = {"a": _row("a"), "b": _row("b")}
    decisions = {row_id: _decision(row_id) for row_id in rows}

    clusters = build_review_clusters(rows, decisions, contexts={"a": _context()})

    assert {cluster.member_ids for cluster in clusters} == {("a",), ("b",)}
    invalid = next(cluster for cluster in clusters if cluster.member_ids == ("b",))
    assert not invalid.packet_eligible
    assert invalid.controlled_difference_fields == ("missing_strict_context",)


def test_unit_mismatch_and_multiple_category_matches_require_exact_strict_context() -> None:
    rows = {"a": _row("a", unit="м"), "b": _row("b", unit="шт")}
    decisions = {row_id: _decision(row_id, warning=Status.UNIT_MISMATCH) for row_id in rows}
    contexts = {
        row_id: _context(
            review_reason="unit_mismatch",
            unit_compatibility_class="unit_mismatch",
            quantity_resolution_mode="cost_only",
        )
        for row_id in rows
    }

    clusters = build_review_clusters(rows, decisions, contexts=contexts)

    assert [cluster.member_ids for cluster in clusters] == [("a", "b")]
    assert clusters[0].controlled_difference_fields == ("normalized_source_unit",)

    decisions = {row_id: _decision(row_id, warning="MULTIPLE_CATEGORY_MATCHES") for row_id in rows}
    contexts = {
        row_id: _context(
            review_reason="multiple_categories",
            normalized_work="exact work" if row_id == "a" else "similar work",
        )
        for row_id in rows
    }
    clusters = build_review_clusters(rows, decisions, contexts=contexts)
    assert {cluster.member_ids for cluster in clusters} == {("a",), ("b",)}
