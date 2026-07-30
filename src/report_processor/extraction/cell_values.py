from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from report_processor.excel import DualWorkbookSession
from report_processor.schema import ColumnResolution, SheetType

from .models import ExtractedCellValue, SourceLocation, ValueProvenance
from .statuses import CellValueStatus, EffectiveValueSource

_SUPPORTED_TYPES = (str, int, float, Decimal, bool, date, datetime, time)


def _is_formula(value: object, data_type: str | None) -> bool:
    return data_type == "f" or (isinstance(value, str) and value.startswith("="))


def _is_excel_error(value: object, data_type: str | None) -> bool:
    del value
    return data_type == "e"


def _failed_value(
    *,
    logical_column: str,
    coordinate: str,
    location: SourceLocation,
    header_text: str | None,
    warning: str,
) -> ExtractedCellValue:
    provenance = ValueProvenance(
        location=location,
        logical_column=logical_column,
        header_text=header_text,
        formula=None,
        cached_value_available=False,
        value_source=EffectiveValueSource.EMPTY.value,
        warnings=(warning,),
    )
    return ExtractedCellValue(
        logical_column=logical_column,
        coordinate=coordinate,
        raw_formula_value=None,
        raw_cached_value=None,
        effective_value=None,
        effective_value_source=EffectiveValueSource.EMPTY.value,
        formula_data_type=None,
        cached_data_type=None,
        is_formula=False,
        is_empty=False,
        is_error=True,
        status=CellValueStatus.VALUE_READ_FAILED.value,
        warnings=(warning,),
        provenance=provenance,
    )


def _cell_payload(cell: object) -> tuple[object, str | None]:
    return getattr(cell, "value", None), getattr(cell, "data_type", None)


def _normalize_formula_value(value: object) -> tuple[object, tuple[str, ...]]:
    """Keep array-formula meaning without retaining openpyxl runtime objects."""

    if type(value).__name__ != "ArrayFormula":
        return value, ()
    text = getattr(value, "text", None)
    reference = getattr(value, "ref", None)
    if not isinstance(text, str):
        return None, ("ARRAY_FORMULA_TEXT_UNAVAILABLE",)
    warnings = (f"ARRAY_FORMULA_REF:{reference}",) if isinstance(reference, str) else ()
    return text, warnings


def extract_cell_pair_value(
    session: DualWorkbookSession,
    *,
    sheet_name: str,
    row_number: int,
    column_resolution: ColumnResolution,
    formula_cell: object,
    cached_cell: object,
    sheet_type: SheetType = SheetType.UNKNOWN,
) -> ExtractedCellValue:
    logical_column = column_resolution.logical_column.value
    coordinate = f"{column_resolution.column_letter}{row_number}"
    location = SourceLocation(
        source_file_id=session.source_file_id,
        filename=session.filename,
        sheet_name=sheet_name,
        sheet_type=sheet_type.value,
        row_number=row_number,
        column_number=column_resolution.column_index,
        column_letter=column_resolution.column_letter,
        coordinate=coordinate,
    )
    try:
        raw_formula, formula_type = _cell_payload(formula_cell)
        raw_cached, cached_type = _cell_payload(cached_cell)
    except (TypeError, ValueError, AttributeError) as exc:
        return _failed_value(
            logical_column=logical_column,
            coordinate=coordinate,
            location=location,
            header_text=column_resolution.header_text,
            warning=f"VALUE_READ_FAILED:{type(exc).__name__}",
        )

    raw_formula, array_warnings = _normalize_formula_value(raw_formula)
    is_formula = _is_formula(raw_formula, formula_type)
    formula_error = _is_excel_error(raw_formula, formula_type)
    cached_error = _is_excel_error(raw_cached, cached_type)
    warnings: list[str] = list(array_warnings)

    if formula_error or cached_error:
        effective_value = None
        source = EffectiveValueSource.EXCEL_ERROR
        status = CellValueStatus.EXCEL_ERROR
        is_error = True
        warnings.append("EXCEL_ERROR_VALUE")
    elif is_formula and raw_cached is not None:
        effective_value = raw_cached
        source = EffectiveValueSource.CACHED_FORMULA_VALUE
        status = CellValueStatus.FORMULA_WITH_CACHED_VALUE
        is_error = False
    elif is_formula:
        effective_value = None
        source = EffectiveValueSource.FORMULA_WITHOUT_CACHE
        status = CellValueStatus.FORMULA_WITHOUT_CACHED_VALUE
        is_error = False
        warnings.append("FORMULA_WITHOUT_CACHED_VALUE")
    elif raw_formula is None:
        effective_value = None
        source = EffectiveValueSource.EMPTY
        status = CellValueStatus.EMPTY
        is_error = False
    else:
        effective_value = raw_formula
        source = EffectiveValueSource.LITERAL
        status = CellValueStatus.OK
        is_error = False
        if not isinstance(raw_formula, _SUPPORTED_TYPES):
            status = CellValueStatus.UNSUPPORTED_VALUE_TYPE
            warnings.append(f"UNSUPPORTED_VALUE_TYPE:{type(raw_formula).__name__}")

    formula = raw_formula if is_formula and isinstance(raw_formula, str) else None
    provenance = ValueProvenance(
        location=location,
        logical_column=logical_column,
        header_text=column_resolution.header_text,
        formula=formula,
        cached_value_available=is_formula and raw_cached is not None and not cached_error,
        value_source=source.value,
        warnings=tuple(warnings),
    )
    return ExtractedCellValue(
        logical_column=logical_column,
        coordinate=coordinate,
        raw_formula_value=raw_formula,
        raw_cached_value=raw_cached,
        effective_value=effective_value,
        effective_value_source=source.value,
        formula_data_type=formula_type,
        cached_data_type=cached_type,
        is_formula=is_formula,
        is_empty=status is CellValueStatus.EMPTY,
        is_error=is_error,
        status=status.value,
        warnings=tuple(warnings),
        provenance=provenance,
    )


def extract_cell_value(
    session: DualWorkbookSession,
    *,
    sheet_name: str,
    row_number: int,
    column_resolution: ColumnResolution,
    sheet_type: SheetType = SheetType.UNKNOWN,
) -> ExtractedCellValue:
    coordinate = f"{column_resolution.column_letter}{row_number}"
    try:
        formula_cell = session.formula_workbook[sheet_name][coordinate]
        cached_cell = session.values_workbook[sheet_name][coordinate]
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        location = SourceLocation(
            source_file_id=session.source_file_id,
            filename=session.filename,
            sheet_name=sheet_name,
            sheet_type=sheet_type.value,
            row_number=row_number,
            column_number=column_resolution.column_index,
            column_letter=column_resolution.column_letter,
            coordinate=coordinate,
        )
        return _failed_value(
            logical_column=column_resolution.logical_column.value,
            coordinate=coordinate,
            location=location,
            header_text=column_resolution.header_text,
            warning=f"VALUE_READ_FAILED:{type(exc).__name__}",
        )
    return extract_cell_pair_value(
        session,
        sheet_name=sheet_name,
        row_number=row_number,
        column_resolution=column_resolution,
        formula_cell=formula_cell,
        cached_cell=cached_cell,
        sheet_type=sheet_type,
    )
