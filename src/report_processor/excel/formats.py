from __future__ import annotations

import zipfile
from pathlib import Path

from report_processor.domain.statuses import StatusCode

from .models import ExcelFormatResult

_FORMATS = {
    ".xlsx": ("Office Open XML", True, False),
    ".xlsm": ("Office Open XML Macro", True, True),
    ".xls": ("Binary Excel 97–2003", False, False),
    ".xlsb": ("Excel Binary Workbook", False, False),
    ".ods": ("OpenDocument Spreadsheet", False, False),
}


def detect_excel_format(path: Path) -> ExcelFormatResult:
    path = Path(path)
    extension = path.suffix.lower()
    format_name, supported, macro_enabled = _FORMATS.get(
        extension, ("Unknown spreadsheet format", False, False)
    )
    warnings: list[str] = []
    if extension in {".xlsx", ".xlsm"} and not zipfile.is_zipfile(path):
        supported = False
        warnings.append(StatusCode.INVALID_XLSX_CONTAINER.value)
    elif extension not in _FORMATS:
        warnings.append(StatusCode.UNSUPPORTED_EXCEL_FORMAT.value)
    return ExcelFormatResult(
        extension=extension,
        format_name=format_name,
        supported=supported,
        macro_enabled=macro_enabled,
        warnings=tuple(warnings),
    )
