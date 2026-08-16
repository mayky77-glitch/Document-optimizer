"""Structural source-header regression contracts."""

from __future__ import annotations

from openpyxl import Workbook

from report_processor.admin_panel.reconciliation_sources import (
    ReconciliationSourceDescriptor,
    _extract_ks2_rows,
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


def test_unrelated_later_merge_does_not_invalidate_cumulative_parent() -> None:
    workbook = Workbook()
    sheet = workbook.active
    formulas = workbook.copy_worksheet(sheet)
    for candidate in (sheet, formulas):
        candidate["B1"] = "Перечень строительных работ"
        candidate["C1"] = "Единица измерения"
        candidate["D1"] = "Выполненные работы нарастающим итогом"
        candidate["D3"] = "Количество"
        candidate["E3"] = "Общая стоимость"
        candidate.append(("", "Монтаж", "м", 2, 10))
    sheet.merge_cells("D1:E2")
    sheet.merge_cells("D10:E10")

    rows = _extract_ks6a_rows(
        sheet, formulas, "source:one", ReconciliationSourceDescriptor("source-1234.xlsx")
    )

    workbook.close()
    assert len(rows) == 1
    assert rows[0].work_name_raw == "монтаж"


def test_broad_work_header_is_selected_outside_cumulative_metric_span() -> None:
    workbook = Workbook()
    sheet = workbook.active
    formulas = workbook.copy_worksheet(sheet)
    for candidate in (sheet, formulas):
        candidate["B1"] = "Перечень строительных работ"
        candidate["C1"] = "Единица измерения"
        candidate["D1"] = "Выполненные работы нарастающим итогом"
        candidate["D3"] = "Объём"
        candidate["E3"] = "Сумма затрат"
        candidate.append(("", "Устройство основания", "м²", 3, 30))
    sheet.merge_cells("D1:E2")

    rows = _extract_ks6a_rows(
        sheet, formulas, "source:one", ReconciliationSourceDescriptor("source-1234.xlsx")
    )

    workbook.close()
    assert len(rows) == 1
    assert rows[0].work_name_raw == "устройство основания"
    assert rows[0].cumulative_quantity == 3
    assert rows[0].cumulative_cost == 30


def test_unit_price_leaf_does_not_form_a_metric_pair() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(("", "Наименование работ", "Единица", "Количество", "Цена за единицу"))
    sheet.append(("", "Монтаж", "м", 2, 10))

    assert (
        _extract_ks2_rows(sheet, sheet, "source:one", ReconciliationSourceDescriptor("x.xlsx"))
        == ()
    )
    workbook.close()


def test_cumulative_parent_work_stem_does_not_contaminate_metric_children() -> None:
    workbook = Workbook()
    sheet = workbook.active
    formulas = workbook.copy_worksheet(sheet)
    for candidate in (sheet, formulas):
        candidate.append(("", "Наименование", "Ед. изм.", "Выполнено работ нарастающим итогом", ""))
        candidate.append(("", "работ", "", "Количество", "Общая стоимость"))
        candidate.append(("1", "Монтаж", "м", 2, 10))
    sheet.merge_cells("D1:E1")

    rows = _extract_ks6a_rows(
        sheet, formulas, "source:one", ReconciliationSourceDescriptor("source.xlsx")
    )

    workbook.close()
    assert len(rows) == 1
    assert rows[0].work_name_raw == "монтаж"


def test_split_local_work_and_unit_roles_bind_inside_direct_region_band() -> None:
    workbook = Workbook()
    sheet = workbook.active
    for row in (
        ("", "Наименование", "Единица", "", ""),
        ("", "работ", "измерения", "Количество", "Общая стоимость"),
        ("1", "Монтаж", "м", 2, 10),
    ):
        sheet.append(row)

    rows = _extract_ks2_rows(
        sheet, sheet, "source:one", ReconciliationSourceDescriptor("source.xlsx")
    )

    workbook.close()
    assert len(rows) == 1
    assert rows[0].work_name_raw == "монтаж"


def test_price_lineage_cannot_supply_role_like_unit_descendant() -> None:
    workbook = Workbook()
    sheet = workbook.active
    for row in (
        ("", "Наименование работ", "Цена", "", ""),
        ("", "", "Ед. изм.", "Количество", "Общая стоимость"),
        ("1", "Монтаж", "м", 2, 10),
    ):
        sheet.append(row)

    assert (
        _extract_ks2_rows(sheet, sheet, "source:one", ReconciliationSourceDescriptor("source.xlsx"))
        == ()
    )
    workbook.close()


def test_direct_metric_leaves_below_cumulative_parent_are_rejected() -> None:
    workbook = Workbook()
    sheet = workbook.active
    for row in (
        ("", "Наименование работ", "Ед. изм.", "Выполнено нарастающим итогом", ""),
        ("", "", "", "Количество", "Общая стоимость"),
        ("1", "Монтаж", "м", 2, 10),
    ):
        sheet.append(row)
    sheet.merge_cells("D1:E1")

    assert (
        _extract_ks2_rows(sheet, sheet, "source:one", ReconciliationSourceDescriptor("source.xlsx"))
        == ()
    )
    workbook.close()


def test_column_permutation_does_not_change_physical_role_binding() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(("", "Ед. изм.", "Описание работ", "Количество", "Общая стоимость"))
    sheet.append(("1", "м", "Монтаж", 2, 10))

    rows = _extract_ks2_rows(
        sheet, sheet, "source:one", ReconciliationSourceDescriptor("source.xlsx")
    )

    workbook.close()
    assert len(rows) == 1
    assert rows[0].work_name_raw == "монтаж"
