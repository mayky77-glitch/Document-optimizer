"""Source rows retain their physical worksheet provenance."""

from __future__ import annotations

from openpyxl import Workbook

from report_processor.admin_panel.reconciliation_sources import (
    ReconciliationSourceDescriptor,
    _canonical_rows,
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
