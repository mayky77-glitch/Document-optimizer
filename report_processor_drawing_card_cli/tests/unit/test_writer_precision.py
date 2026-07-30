from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile

from report_processor.drawing_card.output.layout import plan_layout
from report_processor.drawing_card.output.writer import write_card
from report_processor.drawing_card.output.xlsx_xml import _replace_sheet_values

from report_processor.drawing_card.models import (
    CATEGORY_DISPLAY_NAMES,
    CATEGORY_ORDER,
    DrawingCardResultRow,
)
from report_processor.drawing_card.sources.normalization import build_drawing_code
from report_processor.drawing_card.statuses import Status


def test_writer_serializes_decimal_without_binary_float_tail(
    project_root: Path, tmp_path: Path
) -> None:
    drawing = build_drawing_code("DRAW-001")
    rows = []
    for index, category in enumerate(CATEGORY_ORDER):
        rows.append(
            DrawingCardResultRow(
                object_index="0907",
                drawing_code=drawing,
                category=category,
                display_name=CATEGORY_DISPLAY_NAMES[category],
                result_unit="т" if index == 0 else None,
                remaining_quantity=(
                    Decimal("184178.27")
                    if index == 0
                    else Decimal("83108.99")
                    if index == 1
                    else Decimal("0.80978")
                    if index == 2
                    else None
                ),
                remaining_total_cost=(
                    Decimal("37.18943")
                    if index == 0
                    else Decimal("8505987.72")
                    if index == 1
                    else Decimal("8.86")
                    if index == 2
                    else None
                ),
                quantity_source_rows=("row-q",) if index == 0 else (),
                cost_source_rows=("row-c",) if index == 0 else (),
                quantity_rule_id="test-q",
                cost_rule_id="test-c",
                quantity_confidence=1.0,
                cost_confidence=1.0,
                requires_manual_review=False,
                status=Status.OK,
                warnings=(),
            )
        )
    output = tmp_path / "result.xlsx"
    write_card(
        base_path=project_root / "templates" / "default_drawing_card_template.xlsx",
        output_path=output,
        rows=rows,
        layouts=plan_layout(rows),
        run_id="test-run",
        cost_scale=1,
    )
    with ZipFile(output) as archive:
        xml = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "184178.27" in xml
    assert "37.18943" in xml
    assert "184178.269999" not in xml
    assert "37.189430000" not in xml
    assert "83108.99" in xml
    assert "83108.99000000001" not in xml
    assert "0.80978" in xml
    assert "0.8097800000000001" not in xml
    assert "8505987.72" in xml
    assert "8505987.720000001" not in xml
    assert "8.86" in xml
    assert "8.859999999999999" not in xml


def test_xml_rewriter_ignores_self_closing_cells_before_target() -> None:
    data = b'<row><c r="A1"/><c r="B1"><v>1.10000000001</v></c></row>'

    updated, replaced = _replace_sheet_values(data, {"B1": Decimal("1.1")})

    assert updated == b'<row><c r="A1"/><c r="B1"><v>1.1</v></c></row>'
    assert replaced == {"B1"}


def test_xml_rewriter_expands_target_self_closing_numeric_cell() -> None:
    data = b'<row><c r="B1" s="3" t="n"/></row>'

    updated, replaced = _replace_sheet_values(data, {"B1": Decimal("1.1")})

    assert updated == b'<row><c r="B1" s="3" t="n"><v>1.1</v></c></row>'
    assert replaced == {"B1"}


def test_failed_temporary_validation_preserves_existing_output(
    project_root: Path, tmp_path: Path, monkeypatch
) -> None:
    import report_processor.drawing_card.output.writer as writer

    drawing = build_drawing_code("DRAW-001")
    rows = [
        DrawingCardResultRow(
            object_index="0907",
            drawing_code=drawing,
            category=category,
            display_name=CATEGORY_DISPLAY_NAMES[category],
            result_unit=None,
            remaining_quantity=None,
            remaining_total_cost=None,
            quantity_source_rows=(),
            cost_source_rows=(),
            quantity_rule_id="test-q",
            cost_rule_id="test-c",
            quantity_confidence=1.0,
            cost_confidence=1.0,
            requires_manual_review=False,
            status=Status.OK,
            warnings=(),
        )
        for category in CATEGORY_ORDER
    ]
    output = tmp_path / "result.xlsx"
    output.write_bytes(b"previous valid artifact")
    monkeypatch.setattr(
        writer,
        "validate_card",
        lambda *_args: {"status": "OUTPUT_VALIDATION_FAILED", "errors": ["forced"]},
    )

    import pytest

    with pytest.raises(ValueError, match="Temporary output validation failed"):
        write_card(
            base_path=project_root / "templates" / "default_drawing_card_template.xlsx",
            output_path=output,
            rows=rows,
            layouts=plan_layout(rows),
            run_id="test-run",
            cost_scale=1,
        )

    assert output.read_bytes() == b"previous valid artifact"
    assert not list(tmp_path.glob("result.*.tmp.xlsx"))
