"""Synthetic direct-OOXML reporting-period insertion regressions."""

from dataclasses import replace
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill

from report_processor.admin_panel import reconciliation_target_measure
from report_processor.admin_panel.reconciliation_period import ReconciliationPeriodError
from report_processor.excel_writer.period_insertion import (
    _translate_formula,
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


def test_sparse_far_suffix_is_compact_and_part_of_the_immutable_plan(tmp_path: Path) -> None:
    source = tmp_path / "sparse.xlsx"
    _historical_book(source)
    workbook = load_workbook(source)
    workbook["Отчёт"]["Z1000000"] = "far suffix"
    workbook.save(source)

    plan = build_period_insertion_plan(source, "2026-08", {"Отчёт": 3})
    (anchor,) = plan.anchors

    assert anchor.suffix_nonempty_count == 3
    assert anchor.suffix_first_coordinate == "N3"
    assert anchor.suffix_last_coordinate == "Z1000000"
    assert anchor.suffix_rightmost_coordinate == "Z1000000"
    assert len(anchor.suffix_coordinate_sha256) == 64


def test_suffix_rightmost_is_column_major_while_bounds_are_row_major(tmp_path: Path) -> None:
    source = tmp_path / "crossed-axis.xlsx"
    _historical_book(source)
    workbook = load_workbook(source)
    sheet = workbook["Отчёт"]
    sheet["Z4"] = "rightmost"
    sheet["N100"] = "last"
    workbook.save(source)

    (anchor,) = build_period_insertion_plan(source, "2026-08", {"Отчёт": 3}).anchors

    assert anchor.suffix_first_coordinate == "N3"
    assert anchor.suffix_last_coordinate == "N100"
    assert anchor.suffix_rightmost_coordinate == "Z4"


def test_forged_suffix_evidence_is_rejected_before_creating_output(tmp_path: Path) -> None:
    source, output = tmp_path / "source.xlsx", tmp_path / "output.xlsx"
    _historical_book(source)
    plan = build_period_insertion_plan(source, "2026-08", {"Отчёт": 3})
    (anchor,) = plan.anchors
    forged = replace(
        plan,
        anchors=(
            replace(
                anchor,
                historical_parent_label="поддельная историческая подпись",
                suffix_coordinate_sha256="0" * 64,
            ),
        ),
        plan_digest="",
    )
    assert forged.plan_digest != plan.plan_digest

    with pytest.raises(ReconciliationPeriodError, match="PERIOD_INSERTION_PLAN_INVALID"):
        prepare_period_insertion(source, output, forged)

    assert not output.exists()


def test_empty_suffix_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "empty-suffix.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Отчёт"
    sheet["B3"], sheet["C3"], sheet["D3"], sheet["E3"] = "1", "Этап 1", 1, "Монтаж"
    sheet.merge_cells("L1:M1")
    sheet["L1"] = "Документальная отчетность за весь период"
    sheet["L2"], sheet["M2"] = "Количество", "Стоимость"
    workbook.save(source)

    with pytest.raises(ReconciliationPeriodError, match="PERIOD_INSERTION_ANCHOR_INVALID"):
        build_period_insertion_plan(source, "2026-08", {"Отчёт": 3})


def test_suffix_over_limit_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "over-limit.xlsx"
    _historical_book(source)
    monkeypatch.setattr(reconciliation_target_measure, "_MAX_SUFFIX_CELLS", 1)

    with pytest.raises(ReconciliationPeriodError, match="PERIOD_INSERTION_ANCHOR_INVALID"):
        build_period_insertion_plan(source, "2026-08", {"Отчёт": 3})


def test_materialized_cell_inspection_limit_includes_empty_left_cells(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "inspection-limit.xlsx"
    _historical_book(source)
    assert build_period_insertion_plan(source, "2026-08", {"Отчёт": 3}).anchors
    workbook = load_workbook(source)
    sheet = workbook["Отчёт"]
    for column in range(1, 11):
        sheet.cell(20, column).fill = PatternFill("solid", fgColor="FFFFFF")
    workbook.save(source)
    monkeypatch.setattr(reconciliation_target_measure, "_MAX_SUFFIX_INSPECTED_CELLS", 15)

    with pytest.raises(ReconciliationPeriodError, match="PERIOD_INSERTION_ANCHOR_INVALID"):
        build_period_insertion_plan(source, "2026-08", {"Отчёт": 3})


def test_formula_translation_preserves_quoted_coordinate_and_translates_local_range() -> None:
    assert _translate_formula('SUM(L4:N4)+"N4"', 13) == 'SUM(L4:P4)+"N4"'


@pytest.mark.parametrize(
    "formula",
    ("'Другой лист'!N4", "Book.xlsx!N4", "MyNamedRange+N4", 'INDIRECT("N4")'),
)
def test_formula_translation_rejects_nonlocal_or_named_operands(formula: str) -> None:
    with pytest.raises(ReconciliationPeriodError, match="PERIOD_INSERTION_UNSUPPORTED_FEATURE"):
        _translate_formula(formula, 13)


def test_existing_output_sentinel_is_never_replaced(tmp_path: Path) -> None:
    source, output = tmp_path / "source.xlsx", tmp_path / "output.xlsx"
    _historical_book(source)
    output.write_bytes(b"user-sentinel")
    plan = build_period_insertion_plan(source, "2026-08", {"Отчёт": 3})

    with pytest.raises(ReconciliationPeriodError, match="PERIOD_INSERTION_OUTPUT_EXISTS"):
        prepare_period_insertion(source, output, plan)

    assert output.read_bytes() == b"user-sentinel"
