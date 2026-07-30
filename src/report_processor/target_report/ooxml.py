"""Minimal read-only OOXML access used to preserve raw cell lexemes."""

from __future__ import annotations

import posixpath
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_Q = lambda name: f"{{{_MAIN_NS}}}{name}"  # noqa: E731


@dataclass(frozen=True, slots=True)
class RawCellLexemes:
    value: str | None
    formula: str | None
    cell_type: str | None


@dataclass(frozen=True, slots=True)
class SheetStructure:
    dimensions: str | None
    merged_ranges: tuple[str, ...]
    auto_filter_ref: str | None
    freeze_panes: str | None


def _relationship_targets(archive: zipfile.ZipFile) -> dict[str, str]:
    root = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    return {
        item.attrib["Id"]: item.attrib["Target"]
        for item in root.findall(f"{{{_PKG_REL_NS}}}Relationship")
        if "Id" in item.attrib and "Target" in item.attrib
    }


def worksheet_parts(path: Path) -> dict[str, str]:
    """Return sheet title to worksheet XML part without opening for writing."""

    with zipfile.ZipFile(path, "r") as archive:
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        targets = _relationship_targets(archive)
    parts: dict[str, str] = {}
    sheets = workbook.find(_Q("sheets"))
    if sheets is None:
        return parts
    for sheet in sheets.findall(_Q("sheet")):
        name = sheet.attrib.get("name")
        relation = sheet.attrib.get(f"{{{_REL_NS}}}id")
        target = targets.get(relation or "")
        if name and target:
            parts[name] = posixpath.normpath(posixpath.join("xl", target))
    return parts


def read_sheet_lexemes(path: Path, sheet_name: str) -> dict[str, RawCellLexemes]:
    """Read ``<v>`` and ``<f>`` text exactly as represented in worksheet XML."""

    parts = worksheet_parts(path)
    part = parts.get(sheet_name)
    if part is None:
        return {}
    with zipfile.ZipFile(path, "r") as archive:
        root = ElementTree.fromstring(archive.read(part))
    result: dict[str, RawCellLexemes] = {}
    sheet_data = root.find(_Q("sheetData"))
    if sheet_data is None:
        return result
    for cell in sheet_data.iter(_Q("c")):
        coordinate = cell.attrib.get("r")
        if not coordinate:
            continue
        value = cell.findtext(_Q("v"))
        formula = cell.findtext(_Q("f"))
        result[coordinate] = RawCellLexemes(value, formula, cell.attrib.get("t"))
    return result


def read_sheet_structure(path: Path, sheet_name: str) -> SheetStructure:
    """Read structural data unavailable from an openpyxl read-only worksheet."""

    parts = worksheet_parts(path)
    part = parts.get(sheet_name)
    if part is None:
        return SheetStructure(None, (), None, None)
    with zipfile.ZipFile(path, "r") as archive:
        root = ElementTree.fromstring(archive.read(part))
    dimension = root.find(_Q("dimension"))
    merged = root.find(_Q("mergeCells"))
    panes = root.findall(f".//{_Q('pane')}")
    auto_filter = root.find(_Q("autoFilter"))
    return SheetStructure(
        dimension.attrib.get("ref") if dimension is not None else None,
        tuple(item.attrib["ref"] for item in merged or () if "ref" in item.attrib),
        auto_filter.attrib.get("ref") if auto_filter is not None else None,
        panes[0].attrib.get("topLeftCell") if panes else None,
    )


def read_sheet_comments(path: Path, sheet_name: str) -> tuple[tuple[str, str], ...]:
    """Read comment text directly because read-only cells omit comments."""

    part = worksheet_parts(path).get(sheet_name)
    if part is None:
        return ()
    rel_part = posixpath.join(posixpath.dirname(part), "_rels", posixpath.basename(part) + ".rels")
    with zipfile.ZipFile(path, "r") as archive:
        if rel_part not in archive.namelist():
            return ()
        relationships = ElementTree.fromstring(archive.read(rel_part))
        target = next(
            (
                item.attrib.get("Target")
                for item in relationships.findall(f"{{{_PKG_REL_NS}}}Relationship")
                if item.attrib.get("Type", "").endswith("/comments")
            ),
            None,
        )
        if not target:
            return ()
        comment_part = posixpath.normpath(posixpath.join(posixpath.dirname(part), target))
        root = ElementTree.fromstring(archive.read(comment_part))
    return tuple(
        (comment.attrib["ref"], "".join(comment.itertext()))
        for comment in root.findall(f".//{_Q('comment')}")
        if "ref" in comment.attrib
    )


def package_entries(path: Path) -> tuple[str, ...]:
    with zipfile.ZipFile(path, "r") as archive:
        return tuple(sorted(archive.namelist()))
