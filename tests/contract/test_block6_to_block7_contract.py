from decimal import Decimal

from report_processor.extraction.models import CanonicalSourceRow, SourceLocation
from report_processor.training_data import TrainingDataRow, prepare_training_data


def test_block6_canonical_row_is_direct_block7_input():
    source = CanonicalSourceRow(
        row_id="source-row",
        source_type="svvr",
        source_location=SourceLocation(
            source_file_id="file",
            filename="СВВР.xlsx",
            sheet_name="СВВР",
            sheet_type="svvr",
            row_number=25,
        ),
        document_index="0918 (687)",
        document_period="2026-06",
        object_code_raw="ОБ-1",
        object_name_raw=None,
        subobject_code_raw=None,
        subobject_name_raw=None,
        position_code_raw="7",
        work_name_raw="Укладка трубы",
        unit_raw="м",
        contract_quantity=None,
        current_period_quantity=Decimal("12.75"),
        cumulative_quantity=None,
        remaining_quantity=None,
        unit_price=None,
        contract_cost=None,
        current_period_cost=None,
        cumulative_cost=None,
        total_cost=Decimal("150.25"),
        basis_code_raw=None,
        drawing_code_raw="Ч-7",
        cost_type_code_raw=None,
        source_values=(),
        status="OK",
        warnings=(),
    )
    result = prepare_training_data((source,))
    assert len(result.rows) == 1
    assert isinstance(result.rows[0], TrainingDataRow)
    assert result.rows[0].source_row_id == source.row_id
    assert result.rows[0].period_quantity == Decimal("12.75")
    assert result.rows[0].total_cost == Decimal("150.25")
