from pathlib import Path

from report_processor.drawing_card.sources.readers import OpenXmlWorkbookReader
from report_processor.drawing_card.sources.schema import detect_sheet_schema


def test_multiline_remaining_headers_are_resolved(project_root: Path) -> None:
    reader = OpenXmlWorkbookReader(project_root / "examples" / "0906_demo_input.xlsx")
    try:
        schema = detect_sheet_schema(reader, "ВиСР")
    finally:
        reader.close()
    assert schema.header_start_row == 1
    assert schema.header_end_row == 2
    assert schema.columns == {
        "drawing_code": 2,
        "work_name": 3,
        "unit": 4,
        "remaining_quantity": 5,
        "remaining_total_cost": 6,
    }


class _SyntheticReader:
    def __init__(self, rows):
        self.rows = rows

    def list_sheets(self):
        return ("КС-6 ш 0907",)

    def iter_rows(self, sheet_name, **_kwargs):
        assert sheet_name == "КС-6 ш 0907"
        yield from self.rows

    def close(self):
        return None


def test_suspicious_cost_like_quantity_is_replaced_by_valid_residual_triplet() -> None:
    width = 12

    def row(values):
        result = [None] * width
        for column, value in values.items():
            result[column - 1] = value
        return tuple(result)

    rows = [
        (
            row(
                {
                    1: "Шифр чертежа",
                    2: "Наименование этапа выполнения работ",
                    3: "Ед. изм.",
                    4: "Количество",
                    5: "Стоимость по договору, руб.",
                    10: "ОСТАТОК РАБОТ ПО ДОГОВОРУ",
                }
            ),
            row(
                {
                    1: "Шифр чертежа",
                    2: "Наименование этапа выполнения работ",
                    3: "Ед. изм.",
                    4: "Количество",
                    5: "Стоимость по договору, руб.",
                    10: "ОСТАТОК РАБОТ ПО ДОГОВОРУ",
                }
            ),
        ),
        (row({}), row({})),
        (
            row(
                {
                    5: "Стоимость за единицу",
                    6: "Общая стоимость",
                    10: "Количество",
                    11: "Общая стоимость",
                }
            ),
            row(
                {
                    5: "Стоимость за единицу",
                    6: "Общая стоимость",
                    10: "Количество",
                    11: "Общая стоимость",
                }
            ),
        ),
    ]
    samples = [
        ("0.00477", "263050", "1255"),
        ("3.2", "1000", "3200"),
        ("1.5", "2000", "3000"),
        ("8", "750", "6000"),
    ]
    for index, (quantity, unit_price, cost) in enumerate(samples, 4):
        formula = row(
            {
                1: f"DRAW-{index}",
                2: "Монтаж металлоконструкций",
                3: "т",
                4: f"=K{index}-P{index}-S{index}",
                5: f"=L{index}",
                6: f"=ROUND(D{index}*E{index},0)",
                10: f"=F{index}-G{index}",
                11: f"=F{index}-H{index}",
            }
        )
        cached = row(
            {
                1: f"DRAW-{index}",
                2: "Монтаж металлоконструкций",
                3: "т",
                4: quantity,
                5: unit_price,
                6: cost,
                10: cost,
                11: cost,
            }
        )
        rows.append((formula, cached))

    schema = detect_sheet_schema(_SyntheticReader(rows), "КС-6 ш 0907")
    assert schema.columns["remaining_quantity"] == 4
    assert schema.columns["remaining_total_cost"] == 6
    assert any(item.startswith("SUSPICIOUS_QUANTITY_COST_PAIR") for item in schema.warnings)
    assert any(item.startswith("METRIC_COLUMNS_REPLACED") for item in schema.warnings)
