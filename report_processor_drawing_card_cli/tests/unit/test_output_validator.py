from pathlib import Path

from openpyxl import Workbook
from report_processor.drawing_card.output.validator import validate_card

from report_processor.drawing_card.models import CATEGORY_DISPLAY_NAMES, CATEGORY_ORDER


def test_validator_rejects_categories_out_of_order_and_duplicates(tmp_path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet["B2"] = "Индекс объекта: 0907"
    sheet["B4"] = "DRAW-001"
    names = [CATEGORY_DISPLAY_NAMES[category] for category in CATEGORY_ORDER]
    names[1] = names[0]
    for row, name in enumerate(names, start=4):
        sheet.cell(row, 3).value = name
    path = tmp_path / "invalid.xlsx"
    workbook.save(path)
    workbook.close()

    result = validate_card(path)

    assert result["status"] == "OUTPUT_VALIDATION_FAILED"
    assert any(item.startswith("DRAWING_CATEGORY_DUPLICATE:") for item in result["errors"])
    assert any(item.startswith("DRAWING_CATEGORY_ORDER:") for item in result["errors"])
