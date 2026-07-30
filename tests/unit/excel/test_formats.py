from pathlib import Path

import pytest

from report_processor.domain.statuses import StatusCode
from report_processor.excel.formats import detect_excel_format


def test_xlsx_and_xlsm_are_supported(workbook_path: Path, tmp_path: Path):
    xlsx = detect_excel_format(workbook_path)
    assert xlsx.supported and not xlsx.macro_enabled
    xlsm_path = tmp_path / "sample.xlsm"
    xlsm_path.write_bytes(workbook_path.read_bytes())
    xlsm = detect_excel_format(xlsm_path)
    assert xlsm.supported and xlsm.macro_enabled


@pytest.mark.parametrize("suffix", [".xls", ".xlsb", ".ods"])
def test_known_unsupported_formats_are_recognized(tmp_path: Path, suffix: str):
    path = tmp_path / f"sample{suffix}"
    path.write_bytes(b"data")
    result = detect_excel_format(path)
    assert not result.supported
    assert result.format_name != "Unknown spreadsheet format"


def test_invalid_xlsx_container_is_reported(tmp_path: Path):
    path = tmp_path / "invalid.xlsx"
    path.write_text("not a zip", encoding="utf-8")
    result = detect_excel_format(path)
    assert not result.supported
    assert StatusCode.INVALID_XLSX_CONTAINER.value in result.warnings
