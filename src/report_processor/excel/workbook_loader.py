from __future__ import annotations

import logging
from typing import Any

import openpyxl

from report_processor.domain.exceptions import UnsupportedExcelFormatError, WorkbookOpenError
from report_processor.domain.statuses import StatusCode

from .formats import detect_excel_format
from .models import DualWorkbookSession, WorkbookOpenRequest

LOGGER = logging.getLogger(__name__)


def build_openpyxl_parameters(
    request: WorkbookOpenRequest,
    *,
    data_only: bool,
) -> dict[str, Any]:
    format_result = detect_excel_format(request.source.local_path)
    return {
        "filename": request.source.local_path,
        "read_only": request.read_only,
        "data_only": data_only,
        "keep_links": request.keep_links,
        "keep_vba": format_result.macro_enabled,
    }


def load_dual_workbooks(request: WorkbookOpenRequest) -> DualWorkbookSession:
    format_result = detect_excel_format(request.source.local_path)
    if not format_result.supported:
        status = (
            StatusCode.INVALID_XLSX_CONTAINER
            if StatusCode.INVALID_XLSX_CONTAINER.value in format_result.warnings
            else StatusCode.UNSUPPORTED_EXCEL_FORMAT
        )
        raise UnsupportedExcelFormatError(
            status,
            f"Формат {format_result.extension or '<none>'} не поддерживается",
        )

    formula_parameters = build_openpyxl_parameters(request, data_only=False)
    value_parameters = build_openpyxl_parameters(request, data_only=True)
    LOGGER.debug("openpyxl formula parameters: %s", formula_parameters)
    LOGGER.debug("openpyxl value parameters: %s", value_parameters)
    LOGGER.info("Начало открытия workbook")

    formula_workbook = None
    try:
        formula_workbook = openpyxl.load_workbook(**formula_parameters)
        value_workbook = openpyxl.load_workbook(**value_parameters)
    except (OSError, ValueError, KeyError, TypeError) as error:
        if formula_workbook is not None:
            formula_workbook.close()
        raise WorkbookOpenError(
            StatusCode.WORKBOOK_OPEN_FAILED,
            f"Не удалось открыть Excel-книгу: {error}",
        ) from error
    except Exception as error:
        if formula_workbook is not None:
            formula_workbook.close()
        raise WorkbookOpenError(
            StatusCode.WORKBOOK_OPEN_FAILED,
            f"Openpyxl не смог открыть книгу: {error}",
        ) from error

    return DualWorkbookSession(
        formula_workbook=formula_workbook,
        value_workbook=value_workbook,
        source=request.source,
        format_result=format_result,
        keep_vba=format_result.macro_enabled,
    )
