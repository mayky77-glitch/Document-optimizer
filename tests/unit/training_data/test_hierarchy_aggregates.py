from __future__ import annotations

from decimal import Decimal

from report_processor.extraction.models import CanonicalSourceRow, SourceLocation
from report_processor.training_data import prepare_training_data


def source_row(
    row_id: str,
    row_number: int,
    position: str | None,
    cost: str,
    *,
    object_code: str = "object",
) -> CanonicalSourceRow:
    return CanonicalSourceRow(
        row_id=row_id,
        source_type="ks2",
        source_location=SourceLocation(
            source_file_id="source",
            filename="source.xlsx",
            sheet_name="КС-2",
            sheet_type="ks2",
            row_number=row_number,
        ),
        document_index="01",
        document_period="2026-07",
        object_code_raw=object_code,
        object_name_raw=None,
        subobject_code_raw="subobject",
        subobject_name_raw=None,
        position_code_raw=position,
        work_name_raw="Работа",
        unit_raw="м",
        contract_quantity=None,
        current_period_quantity=Decimal("1"),
        cumulative_quantity=None,
        remaining_quantity=None,
        unit_price=None,
        contract_cost=None,
        current_period_cost=Decimal(cost),
        cumulative_cost=None,
        total_cost=None,
        basis_code_raw=None,
        drawing_code_raw=None,
        cost_type_code_raw=None,
        source_values=(),
        status="OK",
        warnings=(),
    )


def test_reconciliation_excludes_parent_before_training_and_keeps_leaf_source_order() -> None:
    result = prepare_training_data(
        (
            source_row("parent", 10, "6.1", "10"),
            source_row("child", 11, "6.1.3", "10"),
            source_row("near-match", 12, "6.10", "4"),
        )
    )

    assert [row.source_row_id for row in result.rows] == ["child", "near-match"]
    assert sum(row.period_cost or Decimal("0") for row in result.rows) == Decimal("14")


def test_reconciliation_isolates_repeated_numbering_between_objects() -> None:
    result = prepare_training_data(
        (
            source_row("object-a-parent", 10, "1", "10", object_code="A"),
            source_row("object-a-child", 11, "1.1", "10", object_code="A"),
            source_row("object-b-same-code", 12, "1", "5", object_code="B"),
        )
    )

    assert [row.source_row_id for row in result.rows] == [
        "object-a-child",
        "object-b-same-code",
    ]
