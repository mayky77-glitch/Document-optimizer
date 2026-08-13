"""Fail-closed direct OOXML insertion of reconciliation reporting-period columns."""

from __future__ import annotations

import hashlib
import os
import posixpath
import re
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import column_index_from_string, coordinate_from_string, range_boundaries

from report_processor.admin_panel.reconciliation_period import (
    PreparedReconciliationTarget,
    ReconciliationPeriodError,
    ReconciliationPeriodInsertionPlan,
    ReconciliationSheetAnchor,
    ReportingPeriod,
)
from report_processor.admin_panel.reconciliation_target_measure import (
    ReconciliationTargetMeasureError,
    calendar_identities,
    discover_historical_target_measures,
    discover_target_measures,
)
from report_processor.target_report.ooxml import worksheet_parts

_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_Q = lambda name: f"{{{_MAIN}}}{name}"  # noqa: E731
_A1 = re.compile(r"(?<![A-Z0-9_])(?P<col>\$?[A-Z]{1,3})(?P<row>\$?\d+)(?![A-Z0-9_])")
_UNSUPPORTED_FORMULA = re.compile(r"\[|\]|\b(?:INDIRECT|ADDRESS)\s*\(", re.IGNORECASE)
_UNSUPPORTED_PART = re.compile(
    r"(?:^|/)(?:tables|pivotTables|pivotCache|slicers|externalLinks|embeddings|controls|charts)/",
    re.IGNORECASE,
)


def build_period_insertion_plan(
    source_path: Path,
    period: ReportingPeriod | str,
    first_detail_rows: dict[str, int],
    merged_ranges_by_sheet: dict[str, tuple[str, ...]] | None = None,
) -> ReconciliationPeriodInsertionPlan:
    """Freeze the only allowed structural insertion before touching a ZIP."""

    reporting_period = (
        period if isinstance(period, ReportingPeriod) else ReportingPeriod.parse(period)
    )
    source = Path(source_path)
    _reject_package(source)
    parts = worksheet_parts(source)
    sheet_ids = _sheet_id_map(source)
    with source.open("rb") as stream:
        digest = hashlib.sha256(stream.read()).hexdigest()
    workbook = load_workbook(source, read_only=False, data_only=False, keep_links=True)
    try:
        current: set[str] = set()
        missing: set[str] = set()
        for sheet_name, detail_row in first_detail_rows.items():
            try:
                pair = discover_target_measures(
                    workbook, {sheet_name: detail_row}, merged_ranges_by_sheet
                )
            except ReconciliationTargetMeasureError as error:
                if str(error) != "TARGET_CURRENT_PERIOD_PAIR_MISSING":
                    raise ReconciliationPeriodError("PERIOD_INSERTION_ANCHOR_INVALID") from None
                missing.add(sheet_name)
            else:
                if _pair_period_conflict(pair[0], reporting_period):
                    raise ReconciliationPeriodError("REPORTING_PERIOD_CONFLICT")
                current.add(sheet_name)
        if current and missing:
            raise ReconciliationPeriodError("PERIOD_INSERTION_MIXED_STATE")
        if current:
            return ReconciliationPeriodInsertionPlan(
                "ReconciliationPeriodInsertion-1.0",
                digest,
                reporting_period,
                (),
                tuple(parts.items()),
                _affected_parts(source, ()),
                tuple(sorted(first_detail_rows.items())),
                True,
            )
        historical = discover_historical_target_measures(
            workbook, first_detail_rows, merged_ranges_by_sheet
        )
        anchors = tuple(
            ReconciliationSheetAnchor(
                pair.sheet_name,
                sheet_ids[pair.sheet_name],
                parts[pair.sheet_name],
                pair.quantity_column,
                pair.cost_column,
                first_detail_rows[pair.sheet_name],
                pair.parent_span,
                pair.historical_parent_label,
                pair.quantity_leaf_row,
                pair.cost_leaf_row,
                pair.quantity_leaf_label,
                pair.cost_leaf_label,
                pair.suffix_nonempty_count,
                pair.suffix_first_coordinate,
                pair.suffix_last_coordinate,
                pair.suffix_rightmost_coordinate,
                pair.suffix_coordinate_sha256,
            )
            for pair in historical
        )
        _reject_affected_comments(source, anchors)
        _preflight_worksheets(source, anchors)
        return ReconciliationPeriodInsertionPlan(
            "ReconciliationPeriodInsertion-1.0",
            digest,
            reporting_period,
            anchors,
            tuple(parts.items()),
            _affected_parts(source, anchors),
            tuple(sorted(first_detail_rows.items())),
        )
    except ReconciliationPeriodError:
        raise
    except ReconciliationTargetMeasureError as error:
        raise ReconciliationPeriodError("PERIOD_INSERTION_ANCHOR_INVALID") from error
    finally:
        workbook.close()


def prepare_period_insertion(
    source_path: Path,
    output_path: Path,
    plan: ReconciliationPeriodInsertionPlan,
) -> PreparedReconciliationTarget:
    """Transform one private copy, independently verify it, then no-clobber publish."""

    source, output = Path(source_path), Path(output_path)
    _assert_digest(source, plan.source_sha256)
    _validate_plan(source, plan)
    if plan.idempotent:
        raise ReconciliationPeriodError("PERIOD_INSERTION_IDEMPOTENT")
    try:
        descriptor, name = tempfile.mkstemp(
            prefix="period-insertion-", suffix=".xlsx", dir=output.parent
        )
        os.close(descriptor)
        temporary = Path(name)
        _transform_package(source, temporary, plan)
        verify_period_insertion(source, temporary, plan)
        _assert_digest(source, plan.source_sha256)
        os.link(temporary, output)
        temporary.unlink()
        _fsync_directory(output.parent)
        return PreparedReconciliationTarget(str(output), _sha256(output), plan)
    except FileExistsError as error:
        raise ReconciliationPeriodError("PERIOD_INSERTION_OUTPUT_EXISTS") from error
    except ReconciliationPeriodError:
        raise
    except Exception as error:
        raise ReconciliationPeriodError("PERIOD_INSERTION_FAILED") from error
    finally:
        if "temporary" in locals():
            temporary.unlink(missing_ok=True)


def verify_period_insertion(
    source_path: Path, output_path: Path, plan: ReconciliationPeriodInsertionPlan
) -> None:
    """Independent package and inverse-coordinate verification of a frozen plan."""

    source, output = Path(source_path), Path(output_path)
    _assert_digest(source, plan.source_sha256)
    _validate_plan(source, plan)
    anchors = {item.sheet_name: item for item in plan.anchors}
    source_parts = dict(plan.worksheet_parts)
    try:
        with zipfile.ZipFile(source) as before, zipfile.ZipFile(output) as after:
            if tuple(before.namelist()) != tuple(after.namelist()) or after.testzip() is not None:
                raise ReconciliationPeriodError("PERIOD_INSERTION_DELTA_INVALID")
            changed = set(plan.affected_parts)
            for info in before.infolist():
                if info.filename not in changed and before.read(info.filename) != after.read(
                    info.filename
                ):
                    raise ReconciliationPeriodError("PERIOD_INSERTION_DELTA_INVALID")
            for sheet_name, anchor in anchors.items():
                _verify_sheet_delta(
                    before.read(source_parts[sheet_name]),
                    after.read(source_parts[sheet_name]),
                    anchor,
                    plan.period,
                )
        workbook = load_workbook(output, read_only=False, data_only=False, keep_links=True)
        try:
            rows = {anchor.sheet_name: anchor.first_detail_row for anchor in plan.anchors}
            pairs = discover_target_measures(workbook, rows)
            if {(pair.sheet_name, pair.quantity_column, pair.cost_column) for pair in pairs} != {
                (anchor.sheet_name, anchor.cost_column + 1, anchor.cost_column + 2)
                for anchor in plan.anchors
            }:
                raise ReconciliationPeriodError("PERIOD_INSERTION_DETECTOR_INVALID")
        finally:
            workbook.close()
    except ReconciliationPeriodError:
        raise
    except Exception as error:
        raise ReconciliationPeriodError("PERIOD_INSERTION_DELTA_INVALID") from error


def _transform_package(
    source: Path, temporary: Path, plan: ReconciliationPeriodInsertionPlan
) -> None:
    anchors = {item.sheet_name: item for item in plan.anchors}
    parts = dict(plan.worksheet_parts)
    try:
        with (
            zipfile.ZipFile(source) as before,
            zipfile.ZipFile(temporary, "w", allowZip64=True) as after,
        ):
            after.comment = before.comment
            for info in before.infolist():
                payload = before.read(info.filename)
                sheet_name = next(
                    (name for name, part in parts.items() if part == info.filename), None
                )
                if sheet_name in anchors:
                    payload = _transform_sheet(payload, anchors[sheet_name], plan.period)
                elif info.filename == "xl/workbook.xml":
                    payload = _transform_defined_names(payload, anchors)
                elif info.filename == "xl/calcChain.xml":
                    payload = _transform_calc_chain(payload, tuple(parts), anchors)
                after.writestr(info, payload)
        _fsync_file(temporary)
    except ReconciliationPeriodError:
        raise
    except Exception as error:
        raise ReconciliationPeriodError("PERIOD_INSERTION_TRANSFORM_INVALID") from error


def _transform_sheet(
    payload: bytes, anchor: ReconciliationSheetAnchor, period: ReportingPeriod
) -> bytes:
    root = ET.fromstring(payload)
    boundary = anchor.insertion_after_column
    _reject_sheet_features(root, boundary)
    parent_row = _historical_parent_xml_row(root, anchor)
    for node in root.iter():
        if node.tag == _Q("c") and "r" in node.attrib:
            node.attrib["r"] = _map_coordinate(node.attrib["r"], boundary)
        elif node.tag == _Q("f") and node.text:
            node.text = _translate_formula(node.text, boundary)
        elif (
            (node.tag in {_Q("mergeCell"), _Q("conditionalFormatting")} and "ref" in node.attrib)
            or (node.tag == _Q("autoFilter") and "ref" in node.attrib)
            or (node.tag == _Q("dimension") and "ref" in node.attrib)
        ):
            node.attrib["ref"] = _map_range(node.attrib["ref"], boundary)
        elif node.tag in {_Q("pane"), _Q("sheetView")} and "topLeftCell" in node.attrib:
            node.attrib["topLeftCell"] = _map_coordinate(node.attrib["topLeftCell"], boundary)
        elif node.tag == _Q("selection"):
            if "activeCell" in node.attrib:
                node.attrib["activeCell"] = _map_coordinate(node.attrib["activeCell"], boundary)
            if "sqref" in node.attrib:
                node.attrib["sqref"] = _map_range(node.attrib["sqref"], boundary)
        elif node.tag == _Q("col"):
            _map_col(node, boundary)
    sheet_data = root.find(_Q("sheetData"))
    if sheet_data is None:
        raise ReconciliationPeriodError("PERIOD_INSERTION_TRANSFORM_INVALID")
    for row in sheet_data.findall(_Q("row")):
        number = int(row.attrib.get("r", "0"))
        old_cells = {
            _unmap_coordinate(cell.attrib["r"], boundary): cell for cell in row.findall(_Q("c"))
        }
        if not old_cells:
            continue
        inserted = []
        for original_column, new_column in (
            (anchor.quantity_column, boundary + 1),
            (anchor.cost_column, boundary + 2),
        ):
            source_cell = old_cells.get(f"{get_column_letter(original_column)}{number}")
            cell = ET.Element(_Q("c"), {"r": f"{get_column_letter(new_column)}{number}"})
            if source_cell is not None and "s" in source_cell.attrib:
                cell.attrib["s"] = source_cell.attrib["s"]
            if number == parent_row:
                _inline_string(
                    cell,
                    f"{period.label} {'Количество' if new_column == boundary + 1 else 'Стоимость'}",
                )
            inserted.append(cell)
        for cell in inserted:
            row.append(cell)
        row[:] = sorted(row, key=lambda cell: _cell_column(cell.attrib.get("r", "A1")))
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _verify_sheet_delta(
    before: bytes, after: bytes, anchor: ReconciliationSheetAnchor, period: ReportingPeriod
) -> None:
    old, new = ET.fromstring(before), ET.fromstring(after)
    boundary = anchor.insertion_after_column
    old_cells = {cell.attrib["r"]: cell for cell in old.iter(_Q("c")) if "r" in cell.attrib}
    new_cells = {cell.attrib["r"]: cell for cell in new.iter(_Q("c")) if "r" in cell.attrib}
    for coordinate, cell in old_cells.items():
        mapped = _map_coordinate(coordinate, boundary)
        candidate = new_cells.get(mapped)
        if candidate is None or candidate.attrib.get("s") != cell.attrib.get("s"):
            raise ReconciliationPeriodError("PERIOD_INSERTION_DELTA_INVALID")
    parent = _historical_parent_xml_row(old, anchor)
    for column, metric in ((boundary + 1, "Количество"), (boundary + 2, "Стоимость")):
        node = new_cells.get(f"{get_column_letter(column)}{parent}")
        if node is None or "".join(node.itertext()) != f"{period.label} {metric}":
            raise ReconciliationPeriodError("PERIOD_INSERTION_DELTA_INVALID")


def _reject_package(source: Path) -> None:
    try:
        with zipfile.ZipFile(source) as archive:
            names = tuple(archive.namelist())
            if len(names) != len(set(names)) or archive.testzip() is not None:
                raise ReconciliationPeriodError("PERIOD_INSERTION_PACKAGE_INVALID")
            if any(_UNSUPPORTED_PART.search(name) for name in names):
                raise ReconciliationPeriodError("PERIOD_INSERTION_UNSUPPORTED_FEATURE")
    except ReconciliationPeriodError:
        raise
    except Exception as error:
        raise ReconciliationPeriodError("PERIOD_INSERTION_PACKAGE_INVALID") from error


def _sheet_id_map(source: Path) -> dict[str, int]:
    with zipfile.ZipFile(source) as archive:
        root = ET.fromstring(archive.read("xl/workbook.xml"))
    result = {}
    for node in root.iter(_Q("sheet")):
        name, sheet_id = node.attrib.get("name"), node.attrib.get("sheetId")
        if not name or not sheet_id or not sheet_id.isdigit():
            raise ReconciliationPeriodError("PERIOD_INSERTION_PACKAGE_INVALID")
        result[name] = int(sheet_id)
    return result


def _affected_parts(
    source: Path, anchors: tuple[ReconciliationSheetAnchor, ...]
) -> tuple[str, ...]:
    with zipfile.ZipFile(source) as archive:
        names = set(archive.namelist())
    affected = {"xl/workbook.xml", *(anchor.worksheet_part for anchor in anchors)}
    if "xl/calcChain.xml" in names:
        affected.add("xl/calcChain.xml")
    return tuple(sorted(affected))


def _validate_plan(source: Path, plan: ReconciliationPeriodInsertionPlan) -> None:
    """Reject fabricated plans before a temporary output identity exists."""

    if plan.plan_digest != hashlib.sha256(plan.canonical_bytes()).hexdigest():
        raise ReconciliationPeriodError("PERIOD_INSERTION_PLAN_INVALID")
    expected = build_period_insertion_plan(source, plan.period, dict(plan.selected_detail_rows))
    if expected.canonical_bytes() != plan.canonical_bytes():
        raise ReconciliationPeriodError("PERIOD_INSERTION_PLAN_INVALID")
    parts = worksheet_parts(source)
    sheet_ids = _sheet_id_map(source)
    if tuple(parts.items()) != plan.worksheet_parts:
        raise ReconciliationPeriodError("PERIOD_INSERTION_PLAN_INVALID")
    if _affected_parts(source, plan.anchors) != plan.affected_parts:
        raise ReconciliationPeriodError("PERIOD_INSERTION_PLAN_INVALID")
    if len({anchor.sheet_name for anchor in plan.anchors}) != len(plan.anchors):
        raise ReconciliationPeriodError("PERIOD_INSERTION_PLAN_INVALID")
    for anchor in plan.anchors:
        if (
            parts.get(anchor.sheet_name) != anchor.worksheet_part
            or sheet_ids.get(anchor.sheet_name) != anchor.sheet_id
            or anchor.cost_column != anchor.quantity_column + 1
            or anchor.parent_span[1] != anchor.quantity_column
            or anchor.parent_span[3] != anchor.cost_column
            or not anchor.historical_parent_label
            or anchor.suffix_nonempty_count < 1
            or not anchor.suffix_first_coordinate
            or not anchor.suffix_last_coordinate
            or not anchor.suffix_rightmost_coordinate
            or len(anchor.suffix_coordinate_sha256) != 64
        ):
            raise ReconciliationPeriodError("PERIOD_INSERTION_PLAN_INVALID")


def _reject_affected_comments(source: Path, anchors: tuple[ReconciliationSheetAnchor, ...]) -> None:
    """Allow comments left of their sheet boundary; VML visual anchors stay untouched."""

    boundaries = {anchor.sheet_name: anchor.insertion_after_column for anchor in anchors}
    parts = worksheet_parts(source)
    try:
        with zipfile.ZipFile(source) as archive:
            for sheet_name, worksheet_part in parts.items():
                boundary = boundaries.get(sheet_name)
                if boundary is None:
                    continue
                rel = posixpath.join(
                    posixpath.dirname(worksheet_part),
                    "_rels",
                    posixpath.basename(worksheet_part) + ".rels",
                )
                if rel not in archive.namelist():
                    continue
                for item in ET.fromstring(archive.read(rel)):
                    if not item.attrib.get("Type", "").endswith("/comments"):
                        continue
                    target = posixpath.normpath(
                        posixpath.join(
                            posixpath.dirname(worksheet_part), item.attrib.get("Target", "")
                        )
                    ).lstrip("/")
                    for comment in ET.fromstring(archive.read(target)).iter(_Q("comment")):
                        reference = comment.attrib.get("ref")
                        if reference and _cell_column(reference) > boundary:
                            raise ReconciliationPeriodError("PERIOD_INSERTION_UNSUPPORTED_FEATURE")
    except ReconciliationPeriodError:
        raise
    except Exception as error:
        raise ReconciliationPeriodError("PERIOD_INSERTION_PACKAGE_INVALID") from error


def _preflight_worksheets(source: Path, anchors: tuple[ReconciliationSheetAnchor, ...]) -> None:
    """Parse every changing sheet and reject unsupported coordinates before temp creation."""

    try:
        with zipfile.ZipFile(source) as archive:
            for anchor in anchors:
                _reject_sheet_features(
                    ET.fromstring(archive.read(anchor.worksheet_part)),
                    anchor.insertion_after_column,
                )
    except ReconciliationPeriodError:
        raise
    except Exception as error:
        raise ReconciliationPeriodError("PERIOD_INSERTION_PACKAGE_INVALID") from error


def _reject_sheet_features(root: ET.Element, boundary: int) -> None:
    rejected = {_Q(name) for name in ("dataValidations", "tableParts", "drawing", "extLst")}
    if any(node.tag in rejected for node in root.iter()):
        raise ReconciliationPeriodError("PERIOD_INSERTION_UNSUPPORTED_FEATURE")
    for node in root.iter(_Q("mergeCell")):
        if "ref" in node.attrib and _crosses_boundary(node.attrib["ref"], boundary):
            raise ReconciliationPeriodError("PERIOD_INSERTION_UNSUPPORTED_FEATURE")
    for node in root.iter(_Q("conditionalFormatting")):
        if any(child.tag == _Q("formula") for child in node.iter()):
            raise ReconciliationPeriodError("PERIOD_INSERTION_UNSUPPORTED_FEATURE")
    for node in root.iter(_Q("c")):
        formula = node.find(_Q("f"))
        if formula is not None and formula.attrib.get("t") in {"shared", "array", "dataTable"}:
            raise ReconciliationPeriodError("PERIOD_INSERTION_UNSUPPORTED_FEATURE")


def _historical_parent_row(sheet, anchor: ReconciliationSheetAnchor) -> int:
    matches = []
    for merged in sheet.merged_cells.ranges:
        if merged.min_col == anchor.quantity_column and merged.max_col == anchor.cost_column:
            value = sheet.cell(merged.min_row, merged.min_col).value
            if value and any(
                token in str(value).casefold()
                for token in ("истор", "документ", "накоп", "прошл", "весь период")
            ):
                matches.append(merged.min_row)
    if len(matches) != 1:
        raise ReconciliationPeriodError("PERIOD_INSERTION_ANCHOR_INVALID")
    return matches[0]


def _historical_parent_xml_row(root: ET.Element, anchor: ReconciliationSheetAnchor) -> int:
    parent = anchor.parent_span
    for node in root.iter(_Q("mergeCell")):
        ref = node.attrib.get("ref", "")
        try:
            left, top, right, bottom = range_boundaries(ref)
        except ValueError:
            continue
        if (top, left, bottom, right) == parent:
            return top
    if parent[1] != anchor.quantity_column or parent[3] != anchor.cost_column:
        raise ReconciliationPeriodError("PERIOD_INSERTION_ANCHOR_INVALID")
    raise ReconciliationPeriodError("PERIOD_INSERTION_ANCHOR_INVALID")


def _pair_period_conflict(pair, period: ReportingPeriod) -> bool:
    quantity = calendar_identities(pair.quantity_header)
    cost = calendar_identities(pair.cost_header)
    evidence = quantity | cost
    return any(month != period.month or year not in {None, period.year} for month, year in evidence)


def _map_coordinate(coordinate: str, boundary: int) -> str:
    column, row = coordinate_from_string(coordinate.replace("$", ""))
    index = column_index_from_string(column)
    prefix = "$" if coordinate.startswith("$") else ""
    row_prefix = "$" if "$" in coordinate[len(prefix) + len(column) :] else ""
    return f"{prefix}{get_column_letter(index + 2 if index > boundary else index)}{row_prefix}{row}"


def _unmap_coordinate(coordinate: str, boundary: int) -> str:
    column, row = coordinate_from_string(coordinate.replace("$", ""))
    index = column_index_from_string(column)
    return f"{get_column_letter(index - 2 if index > boundary + 2 else index)}{row}"


def _map_range(value: str, boundary: int) -> str:
    if " " in value:
        return " ".join(_map_range(item, boundary) for item in value.split())
    left, top, right, bottom = range_boundaries(value.replace("$", ""))
    if left <= boundary < right:
        right += 2
    elif left > boundary:
        left += 2
        right += 2
    return f"{get_column_letter(left)}{top}:{get_column_letter(right)}{bottom}"


def _crosses_boundary(value: str, boundary: int) -> bool:
    left, _top, right, _bottom = range_boundaries(value.replace("$", ""))
    return left <= boundary < right


def _translate_formula(formula: str, boundary: int) -> str:
    if _UNSUPPORTED_FORMULA.search(formula):
        raise ReconciliationPeriodError("PERIOD_INSERTION_UNSUPPORTED_FEATURE")
    return _A1.sub(lambda match: _map_coordinate(match.group(0), boundary), formula)


def _map_col(node: ET.Element, boundary: int) -> None:
    minimum, maximum = int(node.attrib["min"]), int(node.attrib["max"])
    if minimum <= boundary < maximum:
        node.attrib["max"] = str(maximum + 2)
    elif minimum > boundary:
        node.attrib["min"], node.attrib["max"] = str(minimum + 2), str(maximum + 2)


def _inline_string(cell: ET.Element, text: str) -> None:
    cell.attrib["t"] = "inlineStr"
    inline = ET.SubElement(cell, _Q("is"))
    ET.SubElement(inline, _Q("t")).text = text


def _cell_column(coordinate: str) -> int:
    return column_index_from_string(coordinate_from_string(coordinate)[0])


def _transform_defined_names(
    payload: bytes, anchors: dict[str, ReconciliationSheetAnchor]
) -> bytes:
    root = ET.fromstring(payload)
    for node in root.iter(_Q("definedName")):
        if node.text and "!" in node.text:
            sheet, reference = node.text.rsplit("!", 1)
            name = sheet.strip("'")
            anchor = anchors.get(name)
            if anchor is not None:
                node.text = f"{sheet}!{_map_range(reference, anchor.insertion_after_column)}"
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _transform_calc_chain(
    payload: bytes,
    sheet_names: tuple[str, ...],
    anchors: dict[str, ReconciliationSheetAnchor],
) -> bytes:
    root = ET.fromstring(payload)
    for node in root.iter(_Q("c")):
        index = int(node.attrib.get("i", "1")) - 1
        if not 0 <= index < len(sheet_names):
            raise ReconciliationPeriodError("PERIOD_INSERTION_UNSUPPORTED_FEATURE")
        anchor = anchors.get(sheet_names[index])
        if anchor is not None and "r" in node.attrib:
            node.attrib["r"] = _map_coordinate(node.attrib["r"], anchor.insertion_after_column)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _assert_digest(path: Path, expected: str) -> None:
    if _sha256(path) != expected:
        raise ReconciliationPeriodError("PERIOD_INSERTION_SOURCE_CHANGED")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_file(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
