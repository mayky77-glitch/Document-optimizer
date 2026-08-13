"""Structural current-period target-measure discovery contracts."""

from __future__ import annotations

import pytest
from openpyxl import Workbook

from report_processor.admin_panel.reconciliation_target_measure import (
    ReconciliationTargetMeasureError,
    discover_target_measures,
)


def _workbook():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Отчёт"
    sheet["B3"] = "1234"
    sheet["C3"] = "Этап 13.1"
    sheet["D3"] = "1"
    sheet["E3"] = "Монтаж"
    return workbook, sheet


def _pair(
    sheet,
    start: int,
    parent: str | None,
    quantity: str = "Количество",
    cost: str = "Стоимость",
):
    if parent is not None:
        sheet.merge_cells(start_row=1, start_column=start, end_row=1, end_column=start + 1)
        sheet.cell(1, start).value = parent
    sheet.cell(2, start).value = quantity
    sheet.cell(2, start + 1).value = cost


def test_later_unmerged_same_month_pair_wins_over_historical_documentary_pair() -> None:
    workbook, sheet = _workbook()
    _pair(sheet, 10, "Документальная отчетность за весь период")
    sheet["L1"] = "Август 2026"
    sheet["M1"] = "Август 2026"
    _pair(sheet, 12, None)

    pairs = discover_target_measures(workbook, {sheet.title: 3})

    assert [(pair.quantity_letter, pair.cost_letter) for pair in pairs] == [("L", "M")]


@pytest.mark.parametrize("month", ("Март", "Май"))
def test_month_only_current_pair_wins_over_historical_pair(month: str) -> None:
    workbook, sheet = _workbook()
    _pair(sheet, 10, "Документальная отчетность за весь период")
    sheet["L1"], sheet["M1"] = month, month
    _pair(sheet, 12, None)

    (pair,) = discover_target_measures(workbook, {sheet.title: 3})

    assert (pair.quantity_letter, pair.cost_letter) == ("L", "M")


def test_common_merged_current_parent_is_sufficient_without_calendar_month() -> None:
    workbook, sheet = _workbook()
    _pair(sheet, 12, "Отчетный период")

    (pair,) = discover_target_measures(workbook, {sheet.title: 3})

    assert (pair.quantity_letter, pair.cost_letter) == ("L", "M")


@pytest.mark.parametrize(
    ("left", "right"),
    (("Август 2026", "Сентябрь 2026"), ("Период", "Период")),
)
def test_missing_or_conflicting_period_identity_fails_closed(left: str, right: str) -> None:
    workbook, sheet = _workbook()
    sheet["L1"], sheet["M1"] = left, right
    _pair(sheet, 12, None)

    with pytest.raises(
        ReconciliationTargetMeasureError, match="TARGET_CURRENT_PERIOD_PAIR_MISSING"
    ):
        discover_target_measures(workbook, {sheet.title: 3})


def test_unit_price_and_duplicate_physical_header_evidence_are_not_extra_candidates() -> None:
    workbook, sheet = _workbook()
    _pair(sheet, 10, "Текущий отчетный период", cost="Цена за единицу")
    _pair(sheet, 12, "Текущий отчетный период")
    sheet.merge_cells("L2:L3")
    sheet.merge_cells("M2:M3")

    (pair,) = discover_target_measures(workbook, {sheet.title: 4})

    assert (pair.quantity_letter, pair.cost_letter) == ("L", "M")


@pytest.mark.parametrize(
    ("quantity_header", "cost_header"),
    (
        ("Март Апрель Количество", "Март Апрель Стоимость"),
        ("Март Количество", "Апрель Стоимость"),
    ),
)
def test_multiple_month_mentions_are_not_an_unambiguous_period(
    quantity_header: str, cost_header: str
) -> None:
    workbook, sheet = _workbook()
    sheet["L1"], sheet["M1"] = quantity_header, cost_header

    with pytest.raises(
        ReconciliationTargetMeasureError, match="TARGET_CURRENT_PERIOD_PAIR_MISSING"
    ):
        discover_target_measures(workbook, {sheet.title: 2})


@pytest.mark.parametrize(
    "scope", ("Отчетный период с начала строительства", "Отчетный период итого")
)
def test_cumulative_scope_conflicts_reject_otherwise_current_pair(scope: str) -> None:
    workbook, sheet = _workbook()
    _pair(sheet, 12, scope)

    with pytest.raises(
        ReconciliationTargetMeasureError, match="TARGET_CURRENT_PERIOD_PAIR_MISSING"
    ):
        discover_target_measures(workbook, {sheet.title: 3})


def test_total_cost_leaf_with_vsego_is_not_a_historical_conflict() -> None:
    workbook, sheet = _workbook()
    sheet["L1"], sheet["M1"] = "Май", "Май"
    _pair(sheet, 12, None, cost="Стоимость всего")

    (pair,) = discover_target_measures(workbook, {sheet.title: 3})

    assert (pair.quantity_letter, pair.cost_letter) == ("L", "M")


def test_two_distinct_current_period_pairs_are_ambiguous() -> None:
    workbook, sheet = _workbook()
    _pair(sheet, 12, "Текущий отчетный период")
    _pair(sheet, 14, "Текущий отчетный период")

    with pytest.raises(
        ReconciliationTargetMeasureError, match="TARGET_CURRENT_PERIOD_PAIR_AMBIGUOUS"
    ):
        discover_target_measures(workbook, {sheet.title: 3})


def test_pairs_are_sheet_local_and_can_use_different_columns() -> None:
    workbook, first = _workbook()
    _pair(first, 12, "Текущий отчетный период")
    second = workbook.create_sheet("Дополнение")
    second["B3"], second["C3"], second["D3"], second["E3"] = "1235", "Этап 13.1", "1", "Монтаж"
    _pair(second, 14, "Текущий отчетный период")

    pairs = discover_target_measures(workbook, {first.title: 3, second.title: 3})

    assert [(pair.sheet_name, pair.quantity_letter, pair.cost_letter) for pair in pairs] == [
        ("Дополнение", "N", "O"),
        ("Отчёт", "L", "M"),
    ]
