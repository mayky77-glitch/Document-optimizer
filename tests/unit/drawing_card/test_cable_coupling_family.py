"""Regression contracts for the narrowly anchored cable-coupling rule."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from report_processor.drawing_card.aggregation import aggregate_rows
from report_processor.drawing_card.config import load_rules
from report_processor.drawing_card.matching.matcher import DrawingRowMatcher
from report_processor.drawing_card.models import TargetWorkCategory
from report_processor.drawing_card.statuses import Status

from .test_dictionary_masks import _row

RULES = load_rules(
    Path(__file__).parents[3]
    / "src"
    / "report_processor"
    / "drawing_card"
    / "resources"
    / "rules.json"
)


def _matcher() -> DrawingRowMatcher:
    return DrawingRowMatcher(RULES, (), rag_mode="off")


def test_anchored_cable_coupling_with_cost_is_unique_power_cable_cost_only() -> None:
    row = _row(
        "Установка муфт соединительных кабельных 10 кВ (№2)",
        quantity=Decimal("4"),
        cost=Decimal("1234.50"),
    )

    decision = _matcher().match(row)
    aggregated = aggregate_rows([row], [decision], drawing_code_mode="strict", strict=True)

    assert decision.category is TargetWorkCategory.POWER_CABLE
    assert (decision.quantity_decision, decision.cost_decision) == ("exclude", "include")
    assert decision.matching_strategy == "deterministic_cable_coupling_cost_only"
    assert decision.requires_manual_review is False
    assert aggregated[0].quantity == Decimal()
    assert aggregated[0].total_cost == Decimal("1234.50")


@pytest.mark.parametrize(
    "row",
    [
        _row("Монтаж: установка муфт соединительных кабельных", cost=Decimal("10")),
        replace(
            _row("Установка муфт соединительных кабельных", cost=Decimal("10")),
            formula_values=("=A1",),
            cached_values=(None,),
            warnings=(Status.FORMULA_WITHOUT_CACHED_VALUE,),
        ),
    ],
)
def test_cable_coupling_rule_never_overrides_unsafe_or_non_anchored_inputs(row) -> None:
    decision = _matcher().match(row)

    assert decision.matching_strategy != "deterministic_cable_coupling_cost_only"
    if row.warnings:
        assert decision.requires_manual_review is True
        assert Status.FORMULA_WITHOUT_CACHED_VALUE in decision.warnings


@pytest.mark.parametrize("cost", [None, Decimal("0"), Decimal("-10")])
def test_cable_coupling_without_positive_cost_stays_fail_closed(
    cost: Decimal | None,
) -> None:
    decision = _matcher().match(_row("Установка муфт соединительных кабельных 10 кВ", cost=cost))

    assert decision.category is TargetWorkCategory.POWER_CABLE
    assert (decision.quantity_decision, decision.cost_decision) == ("review", "review")
    assert decision.matching_strategy == "review"
    assert decision.requires_manual_review is True
