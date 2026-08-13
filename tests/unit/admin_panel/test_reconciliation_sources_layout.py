"""Structural source-header regression contracts."""

from __future__ import annotations

from openpyxl import Workbook

from report_processor.admin_panel.reconciliation_sources import (
    ReconciliationSourceDescriptor,
    _extract_ks6a_rows,
)


def test_merged_cumulative_parent_binds_adjacent_quantity_and_total_cost() -> None:
    workbook = Workbook()
    sheet = workbook.active
    formulas = workbook.copy_worksheet(sheet)
    sheet.merge_cells("B1:B3")
    sheet.merge_cells("C1:C3")
    sheet.merge_cells("D1:E2")
    for candidate in (sheet, formulas):
        candidate["B1"] = "Наименование работ"
        candidate["C1"] = "Единица измерения"
        candidate["D1"] = "Выполнено нарастающим итогом"
        candidate["D3"] = "Количество"
        candidate["E3"] = "Общая стоимость"
        candidate.append(("", "Монтаж", "м", 2, 10))

    rows = _extract_ks6a_rows(
        sheet, formulas, "source:one", ReconciliationSourceDescriptor("source-1234.xlsx")
    )

    workbook.close()
    assert len(rows) == 1
    assert rows[0].cumulative_quantity == 2
    assert rows[0].cumulative_cost == 10


def test_unit_price_leaf_does_not_form_a_metric_pair() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(("", "Наименование работ", "Единица", "Количество", "Цена за единицу"))
    sheet.append(("", "Монтаж", "м", 2, 10))

    from report_processor.admin_panel.reconciliation_sources import _extract_ks2_rows

    assert (
        _extract_ks2_rows(sheet, sheet, "source:one", ReconciliationSourceDescriptor("x.xlsx"))
        == ()
    )
    workbook.close()
