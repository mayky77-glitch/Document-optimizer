"""Post-write validation of drawing-card workbooks."""

from __future__ import annotations

import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree import ElementTree as ET

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from ..models import CATEGORY_DISPLAY_NAMES, CATEGORY_ORDER, ObjectBlockLayout
from ..sources.normalization import is_plausible_drawing_code, normalize_text
from ..statuses import Status
from .xlsx_xml import find_binary_tail_cells

_EXPECTED_CATEGORIES = tuple(
    normalize_text(CATEGORY_DISPLAY_NAMES[category]) for category in CATEGORY_ORDER
)
_FORMULA_ERRORS = {"#DIV/0!", "#N/A", "#NAME?", "#NULL!", "#NUM!", "#REF!", "#VALUE!"}


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _equal_nonzero(left: Decimal | None, right: Decimal | None) -> bool:
    if left in (None, Decimal(0)) or right in (None, Decimal(0)):
        return False
    tolerance = max(Decimal("0.000001"), abs(right) * Decimal("1e-9"))
    return abs(left - right) <= tolerance


def _validate_archive(path: Path, errors: list[str]) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            broken_member = archive.testzip()
            if broken_member:
                errors.append(f"ZIP_CRC_ERROR:{broken_member}")
            for member in archive.namelist():
                if member.endswith(".xml"):
                    ET.fromstring(archive.read(member))
        return not errors
    except (ET.ParseError, OSError, zipfile.BadZipFile) as error:
        errors.append(f"INVALID_XLSX_ARCHIVE:{error}")
        return False


def _validate_categories(
    *, sheet_name: str, drawing: str, categories: list[str], errors: list[str]
) -> None:
    if len(categories) != len(_EXPECTED_CATEGORIES):
        errors.append(f"DRAWING_CATEGORY_COUNT:{sheet_name}:{drawing}:{len(categories)}")
        return
    if len(set(categories)) != len(categories):
        errors.append(f"DRAWING_CATEGORY_DUPLICATE:{sheet_name}:{drawing}")
    if tuple(categories) != _EXPECTED_CATEGORIES:
        errors.append(f"DRAWING_CATEGORY_ORDER:{sheet_name}:{drawing}")


def _validate_layout_contract(
    workbook, layouts: list[ObjectBlockLayout], errors: list[str]
) -> None:
    for layout in layouts:
        if layout.sheet_name not in workbook.sheetnames:
            errors.append(f"MISSING_SHEET:{layout.sheet_name}")
            continue
        sheet = workbook[layout.sheet_name]
        start = layout.start_column
        merge = f"{get_column_letter(start + 3)}2:{get_column_letter(start + 4)}2"
        if merge not in {str(item) for item in sheet.merged_cells.ranges}:
            errors.append(f"MISSING_MERGE:{sheet.title}:{merge}")
        if sheet.cell(2, start).value != f"Индекс объекта: {layout.object_index}":
            errors.append(f"INVALID_OBJECT_HEADER:{sheet.title}:{start}")
        for block in layout.drawing_code_blocks:
            for offset in range(len(CATEGORY_ORDER)):
                row = block.start_row + offset
                quantity = sheet.cell(row, start + 3)
                cost = sheet.cell(row, start + 4)
                expected_quantity_format = (
                    "0"
                    if isinstance(quantity.value, (int, Decimal))
                    and Decimal(str(quantity.value)) == Decimal(str(quantity.value)).to_integral()
                    else "0.###"
                )
                if quantity.number_format != expected_quantity_format:
                    errors.append(f"INVALID_QUANTITY_FORMAT:{sheet.title}:{quantity.coordinate}")
                if cost.number_format != "#,##0.00":
                    errors.append(f"INVALID_COST_FORMAT:{sheet.title}:{cost.coordinate}")
                if not all(sheet.cell(row, column).has_style for column in range(start, start + 5)):
                    errors.append(f"MISSING_DATA_STYLE:{sheet.title}:{row}")
                if sheet.row_dimensions[row].height is None:
                    errors.append(f"MISSING_ROW_DIMENSION:{sheet.title}:{row}")


def _validate_sheet_data(
    sheet, errors: list[str], numeric_targets: dict[str, set[str]]
) -> tuple[int, int]:
    object_count = 0
    drawing_count = 0
    expected_set = set(_EXPECTED_CATEGORIES)
    for start_column in range(2, sheet.max_column + 1, 6):
        value = sheet.cell(2, start_column).value
        if not isinstance(value, str) or "индекс объекта" not in normalize_text(value):
            continue
        object_count += 1
        current_drawing: str | None = None
        categories: list[str] = []
        dual_nonzero = 0
        equal_nonzero = 0
        for row in range(4, sheet.max_row + 1):
            drawing = sheet.cell(row, start_column).value
            category = sheet.cell(row, start_column + 1).value
            if drawing not in (None, ""):
                if not is_plausible_drawing_code(str(drawing)):
                    coordinate = sheet.cell(row, start_column).coordinate
                    errors.append(f"INVALID_DRAWING_CODE:{sheet.title}:{coordinate}:{drawing}")
                if current_drawing is not None:
                    _validate_categories(
                        sheet_name=sheet.title,
                        drawing=current_drawing,
                        categories=categories,
                        errors=errors,
                    )
                current_drawing = str(drawing)
                drawing_count += 1
                categories = []
            if current_drawing is None or category in (None, ""):
                continue
            normalized = normalize_text(str(category))
            if normalized not in expected_set:
                coordinate = sheet.cell(row, start_column + 1).coordinate
                errors.append(f"UNKNOWN_CATEGORY:{sheet.title}:{coordinate}:{category}")
                continue
            categories.append(normalized)
            quantity_cell = sheet.cell(row, start_column + 3)
            cost_cell = sheet.cell(row, start_column + 4)
            numeric_targets.setdefault(sheet.title, set()).update(
                {quantity_cell.coordinate, cost_cell.coordinate}
            )
            quantity = _decimal(quantity_cell.value)
            cost = _decimal(cost_cell.value)
            if quantity not in (None, Decimal(0)) and cost not in (None, Decimal(0)):
                dual_nonzero += 1
                if _equal_nonzero(quantity, cost):
                    equal_nonzero += 1
        if current_drawing is not None:
            _validate_categories(
                sheet_name=sheet.title,
                drawing=current_drawing,
                categories=categories,
                errors=errors,
            )
        if dual_nonzero >= 3 and equal_nonzero / dual_nonzero >= 0.45:
            errors.append(
                f"SUSPICIOUS_IDENTICAL_QUANTITY_COST:{sheet.title}:{equal_nonzero}/{dual_nonzero}"
            )
    return object_count, drawing_count


def validate_card(path: Path, layouts: list[ObjectBlockLayout] | None = None) -> dict[str, object]:
    """Validate a workbook and return machine-readable output publication evidence."""

    errors: list[str] = []
    warnings: list[str] = []
    if not _validate_archive(path, errors):
        return {
            "status": Status.OUTPUT_VALIDATION_FAILED.value,
            "path": str(path),
            "sheets": [],
            "objects": 0,
            "drawings": 0,
            "errors": errors,
            "warnings": warnings,
        }
    try:
        workbook = load_workbook(path, read_only=False, data_only=False)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        errors.append(f"WORKBOOK_REOPEN_FAILED:{error}")
        return {
            "status": Status.OUTPUT_VALIDATION_FAILED.value,
            "path": str(path),
            "sheets": [],
            "objects": 0,
            "drawings": 0,
            "errors": errors,
            "warnings": warnings,
        }
    numeric_targets: dict[str, set[str]] = {}
    try:
        object_count = drawing_count = 0
        for sheet in workbook.worksheets:
            for row in sheet.iter_rows():
                for cell in row:
                    if cell.data_type == "e" or str(cell.value).upper() in _FORMULA_ERRORS:
                        errors.append(f"FORMULA_ERROR:{sheet.title}:{cell.coordinate}:{cell.value}")
            objects, drawings = _validate_sheet_data(sheet, errors, numeric_targets)
            object_count += objects
            drawing_count += drawings
        if layouts:
            _validate_layout_contract(workbook, layouts, errors)
            expected_objects = len({layout.object_index for layout in layouts})
            if object_count != expected_objects:
                errors.append(f"OBJECT_COUNT:{object_count}!={expected_objects}")
            expected_drawings = sum(len(layout.drawing_code_blocks) for layout in layouts)
            if drawing_count != expected_drawings:
                errors.append(f"DRAWING_COUNT:{drawing_count}!={expected_drawings}")
        for sheet_name, coordinate, raw, canonical in find_binary_tail_cells(path, numeric_targets):
            errors.append(
                f"BINARY_FLOAT_SERIALIZATION:{sheet_name}:{coordinate}:{raw}->{canonical}"
            )
        return {
            "status": Status.OK.value if not errors else Status.OUTPUT_VALIDATION_FAILED.value,
            "path": str(path),
            "sheets": workbook.sheetnames,
            "objects": object_count,
            "drawings": drawing_count,
            "errors": errors,
            "warnings": warnings,
        }
    finally:
        workbook.close()
