"""Read-only structural historical-period target preview regressions."""

from __future__ import annotations

from hashlib import sha256

import pytest
from openpyxl import Workbook

from report_processor.admin_panel.reconciliation_period import ReportingPeriod
from report_processor.admin_panel.reconciliation_period_preview import (  # type: ignore[import-not-found]
    preview_reconciliation_target,
)
from report_processor.admin_panel.reconciliation_target import (
    ReconciliationTargetIdentity,
    ReconciliationTargetScopeError,
)
from report_processor.schema import LogicalColumn


def _target(path, *, second_sheet: bool = False, current: bool = False) -> None:
    workbook = Workbook()
    sheets = [workbook.active]
    if second_sheet:
        sheets.append(workbook.create_sheet())
    for index, sheet in enumerate(sheets, start=1):
        sheet.title = f"Отчёт {index}"
        sheet["C1"], sheet["D1"], sheet["E1"], sheet["F1"], sheet["G1"] = (
            "Индекс документа",
            "Номер этапа",
            "Номер п/п",
            "Наименование работ",
            "Единица измерения",
        )
        sheet["C3"], sheet["D3"], sheet["E3"], sheet["F3"], sheet["G3"] = (
            f"12{index}4",
            "Этап 13.1",
            "1",
            f"Монтаж {index}",
            "м",
        )
        if current:
            sheet.merge_cells("L1:M1")
            sheet["L1"] = "Отчетный период"
        else:
            sheet.merge_cells("L1:M1")
            sheet["L1"] = "Документальная отчетность за весь период"
            sheet["N1"] = "Следующий раздел"
        sheet["L2"], sheet["M2"] = "Количество", "Стоимость"
    workbook.save(path)
    workbook.close()


def test_historical_preview_projects_future_cells_and_leaves_source_unchanged(tmp_path) -> None:
    target = tmp_path / "historical.xlsx"
    _target(target)
    original = target.read_bytes()

    preview = preview_reconciliation_target(
        target, sha256(original).hexdigest(), "13.1", ReportingPeriod.parse("2026-08")
    )

    assert preview.period.value == "2026-08"
    assert preview.plan is not None
    assert preview.plan.source_sha256 == sha256(original).hexdigest()
    assert target.read_bytes() == original
    (row,) = preview.rows
    assert row.work_name == "Монтаж 1"
    assert row.document_index_normalized == "1214"
    assert row.unit == "м"
    assert row.writable is False
    assert row.cell_for(LogicalColumn.CURRENT_PERIOD_QUANTITY).coordinate == "N3"
    assert row.cell_for(LogicalColumn.CURRENT_PERIOD_COST).coordinate == "O3"
    assert row.cell_for(LogicalColumn.CURRENT_PERIOD_QUANTITY).raw_value is None
    assert row.cell_for(LogicalColumn.CURRENT_PERIOD_COST).status == "VIRTUAL_FUTURE_CELL"


def test_historical_preview_maps_each_sheet_to_its_own_anchor(tmp_path) -> None:
    target = tmp_path / "historical.xlsx"
    _target(target, second_sheet=True)

    preview = preview_reconciliation_target(
        target, sha256(target.read_bytes()).hexdigest(), "13.1", "2026-08"
    )

    assert [anchor.sheet_name for anchor in preview.plan.anchors] == ["Отчёт 1", "Отчёт 2"]
    assert [
        (row.sheet_name, row.cell_for(LogicalColumn.CURRENT_PERIOD_COST).coordinate)
        for row in preview.rows
    ] == [
        ("Отчёт 1", "O3"),
        ("Отчёт 2", "O3"),
    ]


def test_existing_current_pair_keeps_strict_physical_target_identity(tmp_path) -> None:
    target = tmp_path / "current.xlsx"
    _target(target, current=True)
    digest = sha256(target.read_bytes()).hexdigest()

    preview = preview_reconciliation_target(target, digest, "13.1", "2026-08")

    assert preview.period is None
    assert preview.plan is None
    assert preview.rows[0].cell_for(LogicalColumn.CURRENT_PERIOD_QUANTITY).coordinate == "L3"
    assert preview.target_identity == ReconciliationTargetIdentity(digest, "13.1")


def test_target_identity_is_canonical_and_period_plan_bound() -> None:
    first = ReconciliationTargetIdentity("original", "13.1", "2026-08", "plan")

    assert (
        first.target_identity_digest
        == ReconciliationTargetIdentity(
            "original", "13.1", "2026-08", "plan"
        ).target_identity_digest
    )
    assert (
        first.target_identity_digest
        != ReconciliationTargetIdentity(
            "original", "13.1", "2026-09", "plan"
        ).target_identity_digest
    )
    assert (
        first.target_identity_digest
        != ReconciliationTargetIdentity("changed", "13.1", "2026-08", "plan").target_identity_digest
    )
    assert (
        first.target_identity_digest
        != ReconciliationTargetIdentity(
            "original", "13.2", "2026-08", "plan"
        ).target_identity_digest
    )


def test_missing_or_tied_base_roles_fail_closed(tmp_path) -> None:
    target = tmp_path / "missing.xlsx"
    _target(target)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Отчёт"
    sheet["C1"], sheet["D1"], sheet["E1"], sheet["F1"] = (
        "Индекс документа",
        "Номер этапа",
        "Номер п/п",
        "Наименование работ",
    )
    workbook.save(target)
    workbook.close()

    with pytest.raises(ReconciliationTargetScopeError, match="BASE_ROLE_MISSING"):
        preview_reconciliation_target(
            target, sha256(target.read_bytes()).hexdigest(), "13.1", "2026-08"
        )

    _target(target)
    from openpyxl import load_workbook

    workbook = load_workbook(target)
    workbook["Отчёт 1"]["H1"] = "Единица измерения"
    workbook.save(target)
    workbook.close()
    with pytest.raises(ReconciliationTargetScopeError, match="BASE_ROLE_AMBIGUOUS"):
        preview_reconciliation_target(
            target, sha256(target.read_bytes()).hexdigest(), "13.1", "2026-08"
        )
