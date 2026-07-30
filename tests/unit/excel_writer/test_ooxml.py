"""Low-level no-clobber and targeted XML preservation tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from report_processor.excel_writer import ExcelWriterIntegrityError, ExcelWriterSafetyError
from report_processor.excel_writer.ooxml import inspect_cell, publish_no_clobber, replace_cell_value

_SHEET_XML = (
    b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    b'<sheetData><row r="30"><c r="D30" s="5"><v>12.50</v></c>'
    b'<c r="E30" s="7"><f>SUM(D30)</f><v>12.50</v></c></row></sheetData></worksheet>'
)


def test_targeted_cell_replacement_preserves_style_formula_and_other_cell_bytes() -> None:
    updated = replace_cell_value(_SHEET_XML, "D30", "-0.250")

    cell, lexeme, is_formula, has_style, cell_type = inspect_cell(updated, "D30")
    assert b's="5"' in cell
    assert lexeme == "-0.250"
    assert not is_formula
    assert has_style
    assert cell_type in {None, "n"}
    assert _SHEET_XML[_SHEET_XML.index(b'<c r="E30"') :] == updated[updated.index(b'<c r="E30"') :]


def test_formula_and_missing_cells_remain_rejectable() -> None:
    _, _, is_formula, _, _ = inspect_cell(_SHEET_XML, "E30")
    assert is_formula
    with pytest.raises(ExcelWriterIntegrityError, match="TARGET_CELL_MISSING"):
        inspect_cell(_SHEET_XML, "D31")


def test_publish_no_clobber_keeps_existing_output_and_removes_temp(tmp_path: Path) -> None:
    temp_path = tmp_path / ".candidate.xlsx.tmp"
    output_path = tmp_path / "published.xlsx"
    temp_path.write_bytes(b"new")
    output_path.write_bytes(b"existing")

    with pytest.raises(ExcelWriterSafetyError, match="OUTPUT_EXISTS"):
        publish_no_clobber(temp_path, output_path)

    assert output_path.read_bytes() == b"existing"
    assert not temp_path.exists()
