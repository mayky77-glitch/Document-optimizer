"""Package-level preservation checks for the frozen XLSX writer contract."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from openpyxl import Workbook
from openpyxl.styles import Font
from report_processor.excel_writer.ooxml import (
    verify_temp_package,
    worksheet_part_map,
    write_temp_package,
)


def _new_styled_workbook(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Лист"
    sheet["D30"] = 12.5
    sheet["D30"].font = Font(bold=True)
    sheet["E30"] = "=D30"
    sheet.merge_cells("A1:B1")
    sheet.freeze_panes = "A2"
    workbook.save(path)


def _parts(path: Path) -> dict[str, bytes]:
    with ZipFile(path) as package:
        return {name: package.read(name) for name in package.namelist()}


def test_targeted_package_write_keeps_unchanged_parts_and_formula_style_merge_metadata(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "source.xlsx"
    temp_path = tmp_path / ".output.xlsx"
    _new_styled_workbook(source_path)
    source_parts = _parts(source_path)
    worksheet_part = worksheet_part_map(source_path)["Лист"]
    changes = {worksheet_part: (("D30", "-0.250"),)}

    write_temp_package(source_path, temp_path, changes)
    verify_temp_package(source_path, temp_path, changes)

    output_parts = _parts(temp_path)
    assert tuple(source_parts) == tuple(output_parts)
    assert all(
        output_parts[name] == payload
        for name, payload in source_parts.items()
        if name != worksheet_part
    )
    worksheet_xml = output_parts[worksheet_part]
    assert b'<c r="D30" s="1" t="n"><v>-0.250</v></c>' in worksheet_xml
    assert b"<f>D30</f>" in worksheet_xml
    assert b'ref="A1:B1"' in worksheet_xml
