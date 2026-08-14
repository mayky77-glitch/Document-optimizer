"""Read-only structural historical-period target preview regressions."""

from __future__ import annotations

import zipfile
from contextlib import contextmanager
from hashlib import sha256
from xml.etree import ElementTree as ET

import pytest
from openpyxl import Workbook, load_workbook

from report_processor.admin_panel import reconciliation_period_preview
from report_processor.admin_panel import reconciliation_target as reconciliation_target_module
from report_processor.admin_panel.reconciliation_period import ReportingPeriod
from report_processor.admin_panel.reconciliation_period_preview import (  # type: ignore[import-not-found]
    preview_reconciliation_target,
)
from report_processor.admin_panel.reconciliation_target import (
    ReconciliationTargetIdentity,
    ReconciliationTargetScopeError,
    read_reconciliation_target,
)
from report_processor.excel_writer import engine as writer_engine
from report_processor.schema import LogicalColumn, SheetType


def _digest(value: str) -> str:
    return sha256(value.encode()).hexdigest()


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
    assert [
        binding.logical_column
        for binding in preview.schema.column_bindings
        if binding.logical_column
        in {
            LogicalColumn.DOCUMENT_INDEX,
            LogicalColumn.STAGE,
            LogicalColumn.ROW_NUMBER,
            LogicalColumn.WORK_NAME,
            LogicalColumn.UNIT,
        }
    ].count(LogicalColumn.DOCUMENT_INDEX) == 1


def test_partial_unrelated_sheet_is_ignored_but_heterogeneous_participant_fails(tmp_path) -> None:
    target = tmp_path / "historical.xlsx"
    _target(target, second_sheet=True)
    workbook = load_workbook(target)
    unrelated = workbook.create_sheet("Примечания")
    unrelated["A1"] = "Наименование работ"
    workbook.save(target)
    workbook.close()

    preview_reconciliation_target(
        target, sha256(target.read_bytes()).hexdigest(), "13.1", "2026-08"
    )

    workbook = load_workbook(target)
    workbook["Отчёт 2"].insert_cols(1)
    workbook.save(target)
    workbook.close()
    with pytest.raises(ReconciliationTargetScopeError, match="BASE_ROLE_HETEROGENEOUS"):
        preview_reconciliation_target(
            target, sha256(target.read_bytes()).hexdigest(), "13.1", "2026-08"
        )


@pytest.mark.parametrize("header", ("C1", "D1", "E1", "F1", "G1"))
def test_participating_sheet_missing_any_base_role_fails_closed(tmp_path, header) -> None:
    target = tmp_path / "historical.xlsx"
    _target(target, second_sheet=True)
    workbook = load_workbook(target)
    workbook["Отчёт 2"][header] = None
    workbook.save(target)
    workbook.close()

    with pytest.raises(ReconciliationTargetScopeError, match="BASE_ROLE_MISSING"):
        preview_reconciliation_target(
            target, sha256(target.read_bytes()).hexdigest(), "13.1", "2026-08"
        )


def test_blank_unit_summary_is_not_semantic_detail(tmp_path) -> None:
    target = tmp_path / "current.xlsx"
    _target(target, current=True)
    workbook = load_workbook(target)
    workbook["Отчёт 1"]["G3"] = ""
    workbook.save(target)
    workbook.close()

    with pytest.raises(ReconciliationTargetScopeError, match="STAGE_EMPTY"):
        read_reconciliation_target(target, sha256(target.read_bytes()).hexdigest(), "13.1")


def test_existing_current_pair_keeps_strict_physical_target_identity(tmp_path) -> None:
    target = tmp_path / "current.xlsx"
    _target(target, current=True)
    digest = sha256(target.read_bytes()).hexdigest()

    preview = preview_reconciliation_target(target, digest, "13.1", None)

    assert preview.period is None
    assert preview.plan is None
    assert preview.rows[0].cell_for(LogicalColumn.CURRENT_PERIOD_QUANTITY).coordinate == "L3"
    assert preview.target_identity == ReconciliationTargetIdentity(digest, "13.1")


def test_reconciliation_schema_envelopes_are_writer_coherent(tmp_path) -> None:
    current = tmp_path / "current.xlsx"
    _target(current, current=True)
    schema, rows = read_reconciliation_target(
        current, sha256(current.read_bytes()).hexdigest(), "13.1"
    )

    assert schema.status == "OK"
    assert schema.diagnostics == ()
    assert schema.pair_cardinality == "1"
    assert {row.sheet_name for row in rows} == {item.sheet_name for item in schema.worksheets}
    assert {item.sheet_type for item in schema.worksheets} == {SheetType.ADDITIONAL_REPORT}
    writer_engine._validate_schema_identity(
        current, writer_engine._source_identity(current), schema
    )

    historical = tmp_path / "historical.xlsx"
    _target(historical)
    preview = preview_reconciliation_target(
        historical, sha256(historical.read_bytes()).hexdigest(), "13.1", "2026-08"
    )

    assert preview.schema.status == "OK"
    assert preview.schema.diagnostics == ()
    assert preview.schema.pair_cardinality == str(len(preview.plan.anchors))
    assert preview.schema.period_identity.current_period == "2026-08"
    assert {row.sheet_name for row in preview.rows} == {
        item.sheet_name for item in preview.schema.worksheets
    }


def test_target_identity_is_canonical_and_period_plan_bound() -> None:
    original, plan, changed = _digest("original"), _digest("plan"), _digest("changed")
    first = ReconciliationTargetIdentity(original, "13.1", "2026-08", plan)

    assert (
        first.target_identity_digest
        == ReconciliationTargetIdentity(original, "13.1", "2026-08", plan).target_identity_digest
    )
    assert (
        first.target_identity_digest
        != ReconciliationTargetIdentity(original, "13.1", "2026-09", plan).target_identity_digest
    )
    assert (
        first.target_identity_digest
        != ReconciliationTargetIdentity(changed, "13.1", "2026-08", plan).target_identity_digest
    )
    assert (
        first.target_identity_digest
        != ReconciliationTargetIdentity(original, "13.2", "2026-08", plan).target_identity_digest
    )


@pytest.mark.parametrize(
    ("original", "period", "plan"),
    (
        ("A" * 64, None, None),
        (_digest("original"), None, _digest("plan")),
        (_digest("original"), "2026-08", None),
    ),
)
def test_target_identity_rejects_noncanonical_digest_or_unpaired_period(
    original, period, plan
) -> None:
    with pytest.raises(ValueError, match="TARGET_IDENTITY_INVALID"):
        ReconciliationTargetIdentity(original, "13.1", period, plan)


def test_target_identity_canonicalizes_mutable_reporting_period() -> None:
    class MutablePeriod:
        value = "2026-08"

    source = MutablePeriod()
    identity = ReconciliationTargetIdentity(_digest("original"), "13.1", source, _digest("plan"))
    expected = identity.target_identity_digest
    source.value = "2026-09"

    assert identity.reporting_period == "2026-08"
    assert identity.target_identity_digest == expected


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
    workbook = load_workbook(target)
    workbook["Отчёт 1"]["H1"] = "Единица измерения"
    workbook.save(target)
    workbook.close()
    with pytest.raises(ReconciliationTargetScopeError, match="BASE_ROLE_AMBIGUOUS"):
        preview_reconciliation_target(
            target, sha256(target.read_bytes()).hexdigest(), "13.1", "2026-08"
        )


def test_preview_rejects_target_mutated_during_planning(tmp_path, monkeypatch) -> None:
    target = tmp_path / "historical.xlsx"
    _target(target)
    digest = sha256(target.read_bytes()).hexdigest()
    planner = reconciliation_period_preview.build_period_insertion_plan

    def mutate_after_plan(*args, **kwargs):
        plan = planner(*args, **kwargs)
        target.write_bytes(target.read_bytes() + b"changed")
        return plan

    monkeypatch.setattr(
        reconciliation_period_preview, "build_period_insertion_plan", mutate_after_plan
    )

    with pytest.raises(ValueError, match="RECONCILIATION_TARGET_CHANGED"):
        preview_reconciliation_target(target, digest, "13.1", "2026-08")


def test_preview_rejects_duplicate_raw_merge_inventory(tmp_path) -> None:
    target = tmp_path / "historical.xlsx"
    _target(target)
    with zipfile.ZipFile(target) as archive:
        members = {item.filename: archive.read(item.filename) for item in archive.infolist()}
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    root = ET.fromstring(members["xl/worksheets/sheet1.xml"])
    merges = root.find(f"{namespace}mergeCells")
    assert merges is not None
    merges.attrib["count"] = str(len(merges) + 1)
    ET.SubElement(merges, f"{namespace}mergeCell", {"ref": "L1:M1"})
    members["xl/worksheets/sheet1.xml"] = ET.tostring(root)
    with zipfile.ZipFile(target, "w") as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)

    with pytest.raises(ValueError, match="TARGET_HEADER_WINDOW_INVALID"):
        preview_reconciliation_target(
            target, sha256(target.read_bytes()).hexdigest(), "13.1", "2026-08"
        )


def test_current_read_rejects_overlapping_raw_merge_inventory(tmp_path) -> None:
    target = tmp_path / "current.xlsx"
    _target(target, current=True)
    with zipfile.ZipFile(target) as archive:
        members = {item.filename: archive.read(item.filename) for item in archive.infolist()}
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    root = ET.fromstring(members["xl/worksheets/sheet1.xml"])
    merges = root.find(f"{namespace}mergeCells")
    assert merges is not None
    merges.attrib["count"] = str(len(merges) + 1)
    ET.SubElement(merges, f"{namespace}mergeCell", {"ref": "M1:N1"})
    members["xl/worksheets/sheet1.xml"] = ET.tostring(root)
    with zipfile.ZipFile(target, "w") as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)

    with pytest.raises(ValueError, match="TARGET_HEADER_WINDOW_INVALID"):
        read_reconciliation_target(target, sha256(target.read_bytes()).hexdigest(), "13.1")


def _many_row_target(path, *, current: bool) -> None:
    _target(path, current=current)
    workbook = load_workbook(path)
    sheet = workbook["Отчёт 1"]
    for row in range(3, 104):
        if row > 3:
            sheet.cell(row, 5).value = row - 2
            sheet.cell(row, 6).value = f"Монтаж {row}"
            sheet.cell(row, 7).value = "м"
        if current:
            sheet.cell(row, 12).value = row - 2
            sheet.cell(row, 13).value = f"=L{row}*2"
    sheet["A999999"] = "far dimension"
    workbook.save(path)
    workbook.close()


def _instrument_open(monkeypatch, module):
    original = module.open_dual_workbook
    counts = {"formula": 0, "value": 0, "cell": 0}

    @contextmanager
    def instrumented(request):
        with original(request) as session:
            for view, key in (
                (session.formula_workbook, "formula"),
                (session.value_workbook, "value"),
            ):
                for sheet in view.worksheets:
                    source, cell = sheet._get_source, sheet.cell

                    def counted_source(source=source, key=key):
                        counts[key] += 1
                        return source()

                    def counted_cell(*args, cell=cell, **kwargs):
                        counts["cell"] += 1
                        return cell(*args, **kwargs)

                    sheet._get_source = counted_source
                    sheet.cell = counted_cell
            yield session

    monkeypatch.setattr(module, "open_dual_workbook", instrumented)
    return counts


def _bounded_snapshot_cell_access(monkeypatch):
    original = reconciliation_target_module._SnapshotWorksheet.cell
    calls = 0

    def counted(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(reconciliation_target_module._SnapshotWorksheet, "cell", counted)
    return lambda: calls


def _shifted_header_target(path, *, current: bool) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Отчёт"
    sheet["C50"], sheet["D50"], sheet["E50"], sheet["F50"], sheet["G50"] = (
        "Индекс документа",
        "Номер этапа",
        "Номер п/п",
        "Наименование работ",
        "Единица измерения",
    )
    sheet.merge_cells("L50:M50")
    sheet["L50"] = "Отчетный период" if current else "Документальная отчетность за весь период"
    if not current:
        sheet["N50"] = "Следующий раздел"
    sheet["L51"], sheet["M51"] = "Количество", "Стоимость"
    sheet["C52"], sheet["D52"], sheet["E52"], sheet["F52"], sheet["G52"] = (
        "1234",
        "Этап 13.1",
        "1",
        "Монтаж",
        "м",
    )
    if current:
        sheet["L52"], sheet["M52"] = 12, 3.5
    sheet["XFD999999"] = "irrelevant"
    workbook.save(path)
    workbook.close()


def test_current_pair_discovery_ignores_far_dimension_column(tmp_path, monkeypatch) -> None:
    target = tmp_path / "shifted-current.xlsx"
    _shifted_header_target(target, current=True)
    access_count = _bounded_snapshot_cell_access(monkeypatch)

    schema, (row,) = read_reconciliation_target(
        target, sha256(target.read_bytes()).hexdigest(), "13.1"
    )

    assert access_count() < 1_000
    assert schema.pair_cardinality == "1"
    assert row.cell_for(LogicalColumn.CURRENT_PERIOD_QUANTITY).coordinate == "L52"
    assert row.selected_quantity.value == 12


def test_preview_discovery_ignores_far_dimension_column(tmp_path, monkeypatch) -> None:
    target = tmp_path / "shifted-historical.xlsx"
    _shifted_header_target(target, current=False)
    original = target.read_bytes()
    access_count = _bounded_snapshot_cell_access(monkeypatch)

    preview = preview_reconciliation_target(target, sha256(original).hexdigest(), "13.1", "2026-08")

    assert access_count() < 1_000
    assert target.read_bytes() == original
    assert preview.schema.status == "OK"
    assert preview.schema.pair_cardinality == "1"
    assert preview.rows[0].cell_for(LogicalColumn.CURRENT_PERIOD_QUANTITY).coordinate == "N52"


def test_public_reconciliation_read_uses_one_snapshot_parse_per_view(tmp_path, monkeypatch) -> None:
    target = tmp_path / "current-many.xlsx"
    _many_row_target(target, current=True)
    counts = _instrument_open(monkeypatch, reconciliation_target_module)

    schema, rows = read_reconciliation_target(
        target, sha256(target.read_bytes()).hexdigest(), "13.1"
    )

    assert counts == {"formula": 1, "value": 1, "cell": 0}
    assert len(rows) == 101
    assert schema.object_blocks[0].start_row == 3
    assert rows[-1].selected_quantity.value == 101
    assert rows[-1].cell_for(LogicalColumn.CURRENT_PERIOD_COST).formula.formula == "=L103*2"


def test_public_reconciliation_preview_uses_one_snapshot_parse_per_view(
    tmp_path, monkeypatch
) -> None:
    target = tmp_path / "historical-many.xlsx"
    _many_row_target(target, current=False)
    counts = _instrument_open(monkeypatch, reconciliation_period_preview)

    preview = preview_reconciliation_target(
        target, sha256(target.read_bytes()).hexdigest(), "13.1", "2026-08"
    )

    assert counts == {"formula": 1, "value": 1, "cell": 0}
    assert len(preview.rows) == 101
    assert preview.schema.object_blocks[0].start_row == 3
    assert preview.rows[-1].selected_quantity.value is None
    assert preview.rows[-1].cell_for(LogicalColumn.CURRENT_PERIOD_COST).coordinate == "O103"
