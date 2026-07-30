"""Low-level OpenXML safeguards for exact numeric serialization.

``openpyxl`` serializes some ordinary decimals through a binary float and can
write values such as ``83108.99000000001`` into worksheet XML.  Excel displays
those cells correctly because of number formatting, but the raw workbook is not
suitable for an audited financial workflow.  This module patches only the
explicit quantity/cost cells written by the application and leaves all other
parts of the workbook byte-for-byte unchanged.
"""

from __future__ import annotations

import os
import re
import tempfile
import zipfile
from collections.abc import Mapping, Set
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CELL_RE = re.compile(
    rb'(?P<cell><c\b[^>]*?\br="(?P<coord>[A-Z]+[1-9][0-9]*)"[^>]*?(?:/>|>.*?</c>))',
    re.DOTALL,
)
_VALUE_RE = re.compile(rb"(<v>)(?P<value>.*?)(</v>)", re.DOTALL)


def decimal_xml_text(value: Decimal) -> str:
    """Return a plain, non-exponential decimal representation for XLSX XML."""

    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def _worksheet_paths(archive: zipfile.ZipFile) -> dict[str, str]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        item.attrib["Id"]: item.attrib["Target"]
        for item in relationships.findall(f"{{{_PACKAGE_REL_NS}}}Relationship")
    }
    result: dict[str, str] = {}
    for sheet in workbook.findall(f".//{{{_MAIN_NS}}}sheet"):
        relationship_id = sheet.attrib[f"{{{_REL_NS}}}id"]
        target = PurePosixPath(targets[relationship_id].lstrip("/"))
        if not str(target).startswith("xl/"):
            target = PurePosixPath("xl") / target
        result[sheet.attrib["name"]] = str(target)
    return result


def _replace_sheet_values(
    data: bytes,
    replacements: Mapping[str, Decimal],
) -> tuple[bytes, set[str]]:
    expected = set(replacements)
    replaced: set[str] = set()

    def replace_cell(match: re.Match[bytes]) -> bytes:
        coordinate = match.group("coord").decode("ascii")
        value = replacements.get(coordinate)
        if value is None:
            return match.group(0)
        cell = match.group("cell")
        value_match = _VALUE_RE.search(cell)
        replacement = decimal_xml_text(value).encode("ascii")
        if value_match is None:
            if not cell.endswith(b"/>"):
                return match.group(0)
            updated = cell[:-2] + b"><v>" + replacement + b"</v></c>"
            replaced.add(coordinate)
            return updated
        updated = (
            cell[: value_match.start("value")] + replacement + cell[value_match.end("value") :]
        )
        replaced.add(coordinate)
        return updated

    updated = _CELL_RE.sub(replace_cell, data)
    missing = expected - replaced
    if missing:
        raise ValueError(
            "Numeric cells were not found in worksheet XML: " + ", ".join(sorted(missing)[:20])
        )
    return updated, replaced


def rewrite_exact_numeric_cells(
    path: Path,
    replacements: Mapping[tuple[str, str], Decimal],
) -> None:
    """Atomically rewrite audited numeric cells with exact decimal text."""

    if not replacements:
        return
    by_sheet: dict[str, dict[str, Decimal]] = {}
    for (sheet_name, coordinate), value in replacements.items():
        by_sheet.setdefault(sheet_name, {})[coordinate] = value

    with zipfile.ZipFile(path, "r") as source:
        sheet_paths = _worksheet_paths(source)
        path_to_sheet = {value: key for key, value in sheet_paths.items()}
        unknown = set(by_sheet) - set(sheet_paths)
        if unknown:
            raise ValueError(f"Unknown output sheet(s): {sorted(unknown)}")
        with tempfile.NamedTemporaryFile(
            prefix=path.stem + ".xmlfix.",
            suffix=".xlsx",
            dir=path.parent,
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
        try:
            with zipfile.ZipFile(temp_path, "w") as target:
                for info in source.infolist():
                    data = source.read(info.filename)
                    sheet_name = path_to_sheet.get(info.filename)
                    if sheet_name in by_sheet:
                        data, _ = _replace_sheet_values(data, by_sheet[sheet_name])
                    target.writestr(info, data)
            os.replace(temp_path, path)
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise


def _binary_tail_candidate(raw: str) -> Decimal | None:
    """Return the canonical value only for a microscopic <=6-digit tail."""

    if "." not in raw or len(raw.partition(".")[2]) <= 6:
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    for places in range(0, 7):
        candidate = value.quantize(Decimal(1).scaleb(-places))
        if candidate != value and abs(value - candidate) <= Decimal("5e-9"):
            return candidate
    return None


def find_binary_tail_cells(
    path: Path,
    targets: Mapping[str, Set[str]],
) -> tuple[tuple[str, str, str, str], ...]:
    """Find binary-tail values in selected worksheet cells.

    Returns tuples ``(sheet_name, coordinate, raw_value, canonical_value)``.
    """

    findings: list[tuple[str, str, str, str]] = []
    with zipfile.ZipFile(path, "r") as archive:
        sheet_paths = _worksheet_paths(archive)
        for sheet_name, coordinates in targets.items():
            sheet_path = sheet_paths.get(sheet_name)
            if not sheet_path or sheet_path not in archive.namelist():
                continue
            data = archive.read(sheet_path)
            for match in _CELL_RE.finditer(data):
                coordinate = match.group("coord").decode("ascii")
                if coordinate not in coordinates:
                    continue
                value_match = _VALUE_RE.search(match.group("cell"))
                if value_match is None:
                    continue
                raw = value_match.group("value").decode("ascii", errors="replace")
                candidate = _binary_tail_candidate(raw)
                if candidate is not None:
                    findings.append((sheet_name, coordinate, raw, decimal_xml_text(candidate)))
    return tuple(findings)
