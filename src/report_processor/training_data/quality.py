from __future__ import annotations

from report_processor.extraction.models import CanonicalSourceRow
from report_processor.extraction.statuses import CellValueStatus

from .models import DataQualityStatus, FormulaErrorCode


def detect_formula_error(row: CanonicalSourceRow) -> FormulaErrorCode:
    statuses = {value.status for value in row.source_values}
    if CellValueStatus.VALUE_READ_FAILED.value in statuses:
        return FormulaErrorCode.VALUE_READ_FAILED
    if CellValueStatus.EXCEL_ERROR.value in statuses:
        return FormulaErrorCode.EXCEL_ERROR
    if CellValueStatus.FORMULA_WITHOUT_CACHED_VALUE.value in statuses:
        return FormulaErrorCode.FORMULA_WITHOUT_CACHE
    return FormulaErrorCode.NONE


def assess_quality(
    row: CanonicalSourceRow,
    *,
    is_detail: bool,
    formula_error: FormulaErrorCode,
) -> tuple[DataQualityStatus, tuple[str, ...]]:
    warnings: list[str] = list(row.warnings)
    if not is_detail:
        warnings.append("NON_DETAIL_ROW")
    if row.work_name_raw is None:
        warnings.append("WORK_NAME_MISSING")
    if formula_error is FormulaErrorCode.VALUE_READ_FAILED:
        warnings.append("VALUE_READ_FAILED")
        return DataQualityStatus.ERROR, tuple(dict.fromkeys(warnings))
    if formula_error is FormulaErrorCode.EXCEL_ERROR:
        warnings.append("EXCEL_ERROR")
        return DataQualityStatus.ERROR, tuple(dict.fromkeys(warnings))
    if formula_error is FormulaErrorCode.FORMULA_WITHOUT_CACHE:
        warnings.append("FORMULA_WITHOUT_CACHE")
    if is_detail and row.unit_raw is None:
        warnings.append("UNIT_MISSING")
    if is_detail and not any((row.position_code_raw, row.basis_code_raw, row.drawing_code_raw)):
        warnings.append("WEAK_IDENTITY_WITHOUT_POSITION_BASIS_OR_DRAWING")
    status = DataQualityStatus.WARNING if warnings else DataQualityStatus.OK
    return status, tuple(dict.fromkeys(warnings))
