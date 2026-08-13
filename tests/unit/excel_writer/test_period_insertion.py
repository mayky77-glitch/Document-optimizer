"""Synthetic direct-OOXML reporting-period insertion regressions."""

from dataclasses import replace
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

from report_processor.admin_panel.reconciliation_period import ReconciliationPeriodError
from report_processor.excel_writer.period_insertion import (
    build_period_insertion_plan,
    prepare_period_insertion,
)


def _historical_book(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Отчёт"
    sheet["B3"], sheet["C3"], sheet["D3"], sheet["E3"] = "1", "Этап 1", 1, "Монтаж"
    sheet.merge_cells("L1:M1")
    sheet["L1"] = "Документальная отчетность за весь период"
    sheet["L2"], sheet["M2"] = "Количество", "Стоимость"
    sheet["N3"] = "хвост"
    sheet["N4"] = "=L4+M4"
    workbook.save(path)


def test_inserts_unmerged_period_columns_with_parent_row_labels(tmp_path: Path) -> None:
    source, output = tmp_path / "source.xlsx", tmp_path / "output.xlsx"
    _historical_book(source)

    plan = build_period_insertion_plan(source, "2026-08", {"Отчёт": 3})
    prepared = prepare_period_insertion(source, output, plan)

    assert prepared.output_sha256
    workbook = load_workbook(output, data_only=False)
    sheet = workbook["Отчёт"]
    assert sheet["N1"].value == "Август 2026 Количество"
    assert sheet["O1"].value == "Август 2026 Стоимость"
    assert sheet["N2"].value is None and sheet["O2"].value is None
    assert sheet["P3"].value == "хвост"
    assert sheet["P4"].value == "=L4+M4"


def test_plan_digest_is_deterministic_and_rejects_a_forged_digest(tmp_path: Path) -> None:
    source = tmp_path / "source.xlsx"
    _historical_book(source)

    first = build_period_insertion_plan(source, "2026-08", {"Отчёт": 3})
    second = build_period_insertion_plan(source, "2026-08", {"Отчёт": 3})

    assert first.plan_digest == second.plan_digest
    with pytest.raises(ReconciliationPeriodError, match="PERIOD_INSERTION_PLAN_INVALID"):
        replace(first, plan_digest="0" * 64)


def test_current_equivalent_calendar_identity_is_idempotent_and_conflict_fails(
    tmp_path: Path,
) -> None:
    source = tmp_path / "current.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Отчёт"
    sheet["B3"], sheet["C3"], sheet["D3"], sheet["E3"] = "1", "Этап 1", 1, "Монтаж"
    sheet["L1"], sheet["M1"] = "08.2026", "2026-08"
    sheet["L2"], sheet["M2"] = "Количество", "Стоимость"
    workbook.save(source)

    assert build_period_insertion_plan(source, "2026-08", {"Отчёт": 3}).idempotent
    with pytest.raises(ReconciliationPeriodError, match="REPORTING_PERIOD_CONFLICT"):
        build_period_insertion_plan(source, "2026-09", {"Отчёт": 3})
