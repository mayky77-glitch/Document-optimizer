"""Source rows retain their physical worksheet provenance."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from openpyxl import Workbook

from report_processor.admin_panel.reconciliation_execution import _sources
from report_processor.admin_panel.reconciliation_sources import (
    AllReconciliationSourcesUnusableError,
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
    descriptor = descriptor_from_upload_basename("source-1234 (0123).xlsx")

    resolved = resolve_descriptor_identity(descriptor, {"0123"})

    assert resolved.document_index == "0123"
    assert resolve_descriptor_identity(descriptor, {"1234", "0123"}).document_index is None


def test_parenthetical_source_identities_allow_exact_three_or_four_digits() -> None:
    descriptor = descriptor_from_upload_basename("1004 (946, 680)_source.xlsx")

    assert descriptor.document_index_candidates == ("1004", "946", "680")
    assert descriptor.document_index is None
    assert resolve_descriptor_identity(descriptor, {"946"}).document_index == "946"
    assert resolve_descriptor_identity(descriptor, {"946", "680"}).document_index is None


def test_three_digit_parenthetical_identity_survives_production_intersection(tmp_path) -> None:
    source = tmp_path / "stored-source.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(("", "Перечень работ", "Единица измерения", "Количество", "Стоимость"))
    sheet.append(("", "Монтаж", "м", 1, 10))
    workbook.save(source)
    workbook.close()
    job = SimpleNamespace(
        sources=(source,),
        source=source,
        source_names=("1004 (946, 680)_source.xlsx",),
        source_digests=("a" * 64,),
    )

    batch = _sources(job, {"946"})

    assert batch.terminal_identities == ((f"source:{'a' * 64}", "946"),)
    with pytest.raises(AllReconciliationSourcesUnusableError) as raised:
        _sources(job, {"946", "680"})
    assert raised.value.issues[0].code == "DOCUMENT_INDEX_MISSING"
