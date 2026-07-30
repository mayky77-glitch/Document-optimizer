from dataclasses import replace
from decimal import Decimal
from itertools import permutations

import pytest

from report_processor.extraction.models import CanonicalSourceRow, SourceLocation
from report_processor.training_data import (
    DataQualityStatus,
    TrainingDataConfig,
    prepare_training_data,
)


def make_row(
    *,
    row_id: str = "row-1",
    row_number: int = 10,
    sheet_name: str = "КС-2",
    work_name: str | None = "Монтаж трубопровода",
    position: str | None = "15",
    unit: str | None = "м",
    quantity: Decimal | None = Decimal("2.5"),
    cost: Decimal | None = Decimal("100.00"),
    total_cost: Decimal | None = None,
) -> CanonicalSourceRow:
    return CanonicalSourceRow(
        row_id=row_id,
        source_type="ks2",
        source_location=SourceLocation(
            source_file_id="file-1",
            filename="0918 КС-2.xlsx",
            sheet_name=sheet_name,
            sheet_type="ks2",
            row_number=row_number,
        ),
        document_index="0918 (687)",
        document_period="2026-06",
        object_code_raw="ОБ-1",
        object_name_raw=None,
        subobject_code_raw="ПД-1",
        subobject_name_raw=None,
        position_code_raw=position,
        work_name_raw=work_name,
        unit_raw=unit,
        contract_quantity=None,
        current_period_quantity=quantity,
        cumulative_quantity=None,
        remaining_quantity=None,
        unit_price=None,
        contract_cost=None,
        current_period_cost=cost,
        cumulative_cost=None,
        total_cost=total_cost,
        basis_code_raw="ГЭСН 01-01",
        drawing_code_raw="Ч-15",
        cost_type_code_raw="СМР",
        source_values=(),
        status="OK",
        warnings=(),
    )


def test_prepares_detail_row_with_stable_identity():
    result = prepare_training_data((make_row(),))
    assert result.statistics.output_rows == 1
    prepared = result.rows[0]
    assert prepared.is_detail is True
    assert prepared.is_total is False
    assert prepared.work_name_normalized == "монтаж трубопровода"
    assert prepared.period_quantity == Decimal("2.5")
    assert prepared.data_quality_status is DataQualityStatus.OK
    assert len(prepared.line_id) == 64


def test_skips_totals_and_outdated_rows_by_default():
    total = make_row(row_id="total", work_name="Итого по разделу", position=None)
    outdated = make_row(row_id="old", sheet_name="ДРДЦ 09 2025 неактуал")
    result = prepare_training_data((total, outdated))
    assert result.rows == ()
    assert result.statistics.skipped_non_detail_rows == 1
    assert result.statistics.skipped_outdated_rows == 1


def test_removes_exact_semantic_duplicate_even_when_source_row_differs():
    first = make_row(row_id="first", row_number=10)
    second = make_row(row_id="second", row_number=11)
    result = prepare_training_data((first, second))
    assert result.statistics.output_rows == 1
    assert result.statistics.exact_duplicates_removed == 1


def test_disambiguates_identity_collision_when_values_differ():
    first = make_row(row_id="first", row_number=10, cost=Decimal("100"))
    second = make_row(row_id="second", row_number=11, cost=Decimal("120"))
    result = prepare_training_data((first, second))
    assert result.statistics.output_rows == 2
    assert result.statistics.line_id_collisions == 1
    assert result.rows[0].line_id != result.rows[1].line_id
    assert result.rows[1].data_quality_status is DataQualityStatus.WARNING


def test_collision_identity_is_stable_when_input_order_changes():
    first = make_row(row_id="first", row_number=10, cost=Decimal("100"))
    second = make_row(row_id="second", row_number=11, cost=Decimal("120"))

    forward = prepare_training_data((first, second))
    reverse = prepare_training_data((second, first))

    forward_ids = {row.source_row_id: row.line_id for row in forward.rows}
    reverse_ids = {row.source_row_id: row.line_id for row in reverse.rows}
    assert forward_ids == reverse_ids


def test_deduplicates_equal_rows_after_an_identity_collision():
    rows = (
        make_row(row_id="a", row_number=10, cost=Decimal("100")),
        make_row(row_id="b", row_number=11, cost=Decimal("120")),
        make_row(row_id="c", row_number=12, cost=Decimal("120")),
    )

    for ordered_rows in permutations(rows):
        result = prepare_training_data(ordered_rows)
        assert result.statistics.output_rows == 2
        assert result.statistics.exact_duplicates_removed == 1
        assert result.statistics.line_id_collisions == 1
        assert len({row.line_id for row in result.rows}) == 2


def test_total_cost_is_preserved_and_prevents_false_deduplication():
    first = make_row(
        row_id="first",
        row_number=10,
        cost=None,
        total_cost=Decimal("100"),
    )
    second = make_row(
        row_id="second",
        row_number=11,
        cost=None,
        total_cost=Decimal("120"),
    )

    result = prepare_training_data((first, second))

    assert [row.total_cost for row in result.rows] == [Decimal("100"), Decimal("120")]
    assert result.statistics.exact_duplicates_removed == 0
    assert result.statistics.line_id_collisions == 1


def test_conflicting_duplicate_source_row_id_is_rejected():
    first = make_row(row_id="duplicate", cost=Decimal("100"))
    second = make_row(row_id="duplicate", cost=Decimal("120"))

    with pytest.raises(ValueError, match="одинаковый row_id"):
        prepare_training_data((first, second))


def test_can_include_non_detail_rows_explicitly():
    row = replace(
        make_row(work_name="Раздел 1", position=None, unit=None, quantity=None, cost=None),
        basis_code_raw=None,
        drawing_code_raw=None,
    )
    result = prepare_training_data((row,), config=TrainingDataConfig(include_non_detail_rows=True))
    assert result.statistics.output_rows == 1
    assert result.rows[0].is_detail is False
