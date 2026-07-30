from report_processor.drawing_card.output.layout import plan_layout

from report_processor.drawing_card.models import (
    CATEGORY_DISPLAY_NAMES,
    DrawingCardResultRow,
    TargetWorkCategory,
)
from report_processor.drawing_card.sources.normalization import build_drawing_code


def _row(object_index: str) -> DrawingCardResultRow:
    category = TargetWorkCategory.PILE_FOUNDATION
    return DrawingCardResultRow(
        object_index=object_index,
        drawing_code=build_drawing_code(f"CODE-{object_index}"),
        category=category,
        display_name=CATEGORY_DISPLAY_NAMES[category],
        result_unit="шт",
        remaining_quantity=None,
        remaining_total_cost=None,
        quantity_source_rows=(),
        cost_source_rows=(),
        quantity_rule_id=None,
        cost_rule_id=None,
        quantity_confidence=None,
        cost_confidence=None,
        requires_manual_review=False,
        status="VALUE_NOT_FOUND",
        warnings=(),
    )


def test_four_objects_use_expected_columns_and_fifth_uses_new_sheet() -> None:
    layouts = plan_layout([_row(value) for value in ("0842", "0845", "0906", "0907", "0918")])
    assert [(item.sheet_name, item.start_column) for item in layouts] == [
        ("Лист1", 2),
        ("Лист1", 8),
        ("Лист1", 14),
        ("Лист1", 20),
        ("Карточка 2", 2),
    ]
