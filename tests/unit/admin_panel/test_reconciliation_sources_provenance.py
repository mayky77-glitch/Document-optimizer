"""Source rows retain their physical worksheet provenance."""

from __future__ import annotations

from openpyxl import Workbook

from report_processor.admin_panel.reconciliation_sources import (
    ReconciliationSourceDescriptor,
    _canonical_rows,
    descriptor_from_upload_basename,
    resolve_descriptor_identity,
)


def test_canonical_rows_keep_the_actual_worksheet_title() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "КС-2 август"
    sheet.append(("Монтаж", "м", 2, 10))
    descriptor = ReconciliationSourceDescriptor("source.xlsx")

    rows = _canonical_rows(
        sheet,
        "source:1",
        descriptor,
        source_type="ks2",
        start_row=1,
        work_column=1,
        unit_column=2,
        quantity_column=3,
        cost_column=4,
        cumulative=False,
    )

    workbook.close()
    assert rows[0].source_location.sheet_name == "КС-2 август"


def test_source_identity_resolves_only_one_selected_target_intersection() -> None:
    descriptor = descriptor_from_upload_basename("акт 1234 (0123).xlsx")

    resolved = resolve_descriptor_identity(descriptor, {"0123"})

    assert resolved.document_index == "0123"
    assert resolve_descriptor_identity(descriptor, {"1234", "0123"}).document_index is None
