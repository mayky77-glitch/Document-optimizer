"""Byte-preserving worksheet-cell changes for XLSX archives."""

from __future__ import annotations

import os
import posixpath
import re
import struct
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import MappingProxyType
from xml.etree import ElementTree
from xml.parsers import expat

from openpyxl import load_workbook

from .exceptions import ExcelWriterAtomicError, ExcelWriterIntegrityError, ExcelWriterSafetyError

_SPREADSHEETML_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_MAX_WORKSHEET_XML_BYTES = 128 * 1024 * 1024
_MAX_WORKSHEET_EVENTS = 2_100_000
_MAX_WORKSHEET_CELLS = 500_000
_MAX_XML_DEPTH = 64
_MAX_ARCHIVE_ENTRIES = 4_096
_MAX_ARCHIVE_MEMBER_BYTES = 256 * 1024 * 1024
_MAX_ARCHIVE_TOTAL_BYTES = 512 * 1024 * 1024
_MAX_COMPRESSION_RATIO = 100
_MAX_INPUT_FILE_BYTES = 256 * 1024 * 1024
_MAX_CENTRAL_DIRECTORY_BYTES = 16 * 1024 * 1024
_CALC_CHAIN_CONTENT_TYPE = re.compile(
    rb'<Override\b(?=[^>]*\bPartName\s*=\s*["\']/xl/calcChain\.xml["\'])[^>]*/>',
    re.IGNORECASE,
)
_A1 = re.compile(r"([A-Z]{1,3})([1-9][0-9]{0,6})\Z")
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


@dataclass(frozen=True, slots=True)
class _ChildSpan:
    """Exact span of a direct SpreadsheetML ``f`` or ``v`` child."""

    qname: bytes
    start: int
    opening_end: int
    end: int
    content_start: int
    content_end: int
    self_closing: bool
    has_children: bool


@dataclass(frozen=True, slots=True)
class _CellSpan:
    """Minimal immutable evidence needed to inspect or rewrite one cell."""

    qname: bytes
    coordinate: str | None
    has_style: bool
    cell_type: str | None
    start: int
    opening_end: int
    end: int
    self_closing: bool
    formula: _ChildSpan | None
    value: _ChildSpan | None
    duplicate_formula: bool
    duplicate_value: bool


@dataclass(slots=True)
class _OpenCell:
    """Parser-local state; converted to a frozen span before the index escapes."""

    name: str
    qname: bytes
    coordinate: str | None
    has_style: bool
    cell_type: str | None
    start: int
    opening_end: int
    formula: _ChildSpan | None = None
    value: _ChildSpan | None = None
    duplicate_formula: bool = False
    duplicate_value: bool = False


@dataclass(slots=True)
class _OpenChild:
    name: str
    qname: bytes
    start: int
    opening_end: int
    parent: _OpenCell
    has_children: bool = False


class _RejectedWorksheetXml(Exception):
    """Internal sentinel for worksheet constructs that must never be expanded."""


@dataclass(frozen=True, slots=True)
class WorksheetIndex:
    """Request-local immutable namespace-aware evidence for one worksheet payload."""

    xml: bytes
    cells: Mapping[str, _CellSpan]
    duplicate_coordinates: frozenset[str]
    cells_without_reference: tuple[_CellSpan, ...]
    formula_count: int


def worksheet_index(xml: bytes, error_code: str = "TARGET_CELL_MISSING") -> WorksheetIndex:
    return _scan_worksheet(xml, error_code)


def _scan_worksheet(xml: bytes, error_code: str = "TARGET_CELL_MISSING") -> WorksheetIndex:
    """Build compact request-local, namespace-aware evidence for one worksheet XML payload."""

    if len(xml) > _MAX_WORKSHEET_XML_BYTES:
        raise ExcelWriterIntegrityError(error_code, "worksheet XML exceeds limit")
    declaration = re.match(rb"<\?xml[^>]*encoding=[\"']([^\"']+)", xml[:200], re.I)
    if declaration is not None and declaration.group(1).lower() not in {b"utf-8", b"utf8"}:
        raise ExcelWriterIntegrityError(error_code, "worksheet encoding unsupported")
    parser = expat.ParserCreate(namespace_separator="}")
    cells: dict[str, _CellSpan] = {}
    duplicate_coordinates: set[str] = set()
    cells_without_reference: list[_CellSpan] = []
    stack: list[tuple[str, _OpenCell | _OpenChild | None]] = []
    events = 0
    cell_count = 0
    formula_count = 0
    root_name: str | None = None
    open_cells = 0

    def start(name: str, attributes: dict[str, str]) -> None:
        nonlocal events, cell_count, formula_count, root_name, open_cells
        events += 1
        if events > _MAX_WORKSHEET_EVENTS:
            raise _RejectedWorksheetXml()
        if len(stack) >= _MAX_XML_DEPTH:
            raise _RejectedWorksheetXml()
        if root_name is None:
            root_name = name
        parent = stack[-1][1] if stack else None
        if isinstance(parent, _OpenChild):
            parent.has_children = True
        if name == _SPREADSHEETML_NS + "}c":
            if open_cells:
                raise _RejectedWorksheetXml()
            cell_count += 1
            if cell_count > _MAX_WORKSHEET_CELLS:
                raise _RejectedWorksheetXml()
        offset = parser.CurrentByteIndex
        opening_end = _opening_tag_end(xml, offset)
        qname = _opening_qname(xml, offset, opening_end)
        if name == _SPREADSHEETML_NS + "}c":
            reference = attributes.get("r")
            if reference is not None and not _valid_a1(reference):
                raise _RejectedWorksheetXml()
            open_cells += 1
            stack.append(
                (
                    name,
                    _OpenCell(
                        name,
                        qname,
                        attributes.get("r"),
                        "s" in attributes,
                        attributes.get("t"),
                        offset,
                        opening_end,
                    ),
                )
            )
        elif name in {_SPREADSHEETML_NS + "}f", _SPREADSHEETML_NS + "}v"}:
            if not isinstance(parent, _OpenCell):
                raise _RejectedWorksheetXml()
            if name.endswith("}f"):
                formula_count += 1
            stack.append((name, _OpenChild(name, qname, offset, opening_end, parent)))
        else:
            stack.append((name, None))

    def end(name: str) -> None:
        nonlocal open_cells
        opened_name, opened = stack.pop()
        if name != opened_name:
            raise _RejectedWorksheetXml()
        offset = parser.CurrentByteIndex
        if isinstance(opened, _OpenChild):
            self_closing = xml[opened.start : opened.opening_end].rstrip().endswith(b"/>")
            span = _ChildSpan(
                opened.qname,
                opened.start,
                opened.opening_end,
                offset if self_closing else _closing_tag_end(xml, offset),
                opened.opening_end,
                opened.opening_end if self_closing else offset,
                self_closing,
                opened.has_children,
            )
            if opened.name.endswith("}f"):
                opened.parent.duplicate_formula = opened.parent.formula is not None
                opened.parent.formula = span
            else:
                opened.parent.duplicate_value = opened.parent.value is not None
                opened.parent.value = span
        elif isinstance(opened, _OpenCell):
            open_cells -= 1
            self_closing = xml[opened.start : opened.opening_end].rstrip().endswith(b"/>")
            cell = _CellSpan(
                opened.qname,
                opened.coordinate,
                opened.has_style,
                opened.cell_type,
                opened.start,
                opened.opening_end,
                offset if self_closing else _closing_tag_end(xml, offset),
                self_closing,
                opened.formula,
                opened.value,
                opened.duplicate_formula,
                opened.duplicate_value,
            )
            reference = cell.coordinate
            if reference is not None:
                if reference in cells:
                    duplicate_coordinates.add(reference)
                else:
                    cells[reference] = cell
            else:
                cells_without_reference.append(cell)

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.StartDoctypeDeclHandler = lambda *_args: (_ for _ in ()).throw(_RejectedWorksheetXml())
    parser.EntityDeclHandler = lambda *_args: (_ for _ in ()).throw(_RejectedWorksheetXml())
    try:
        parser.Parse(xml, True)
    except (expat.ExpatError, IndexError, ValueError, _RejectedWorksheetXml) as error:
        raise ExcelWriterIntegrityError(error_code, "invalid worksheet XML") from error
    if stack:
        raise ExcelWriterIntegrityError(error_code, "unclosed worksheet XML")
    if root_name != _SPREADSHEETML_NS + "}worksheet":
        raise ExcelWriterIntegrityError(error_code, "invalid worksheet root")
    return WorksheetIndex(
        xml,
        MappingProxyType(cells),
        frozenset(duplicate_coordinates),
        tuple(cells_without_reference),
        formula_count,
    )


def _valid_a1(reference: str) -> bool:
    match = _A1.fullmatch(reference)
    if match is None:
        return False
    column = 0
    for letter in match.group(1):
        column = column * 26 + ord(letter) - ord("A") + 1
    return column <= 16_384 and int(match.group(2)) <= 1_048_576


def _opening_tag_end(xml: bytes, start: int) -> int:
    quote: int | None = None
    for index in range(start, len(xml)):
        byte = xml[index]
        if quote is not None:
            if byte == quote:
                quote = None
        elif byte in (ord('"'), ord("'")):
            quote = byte
        elif byte == ord(">"):
            return index + 1
    raise ValueError("unterminated opening tag")


def _closing_tag_end(xml: bytes, start: int) -> int:
    end = xml.find(b">", start)
    if end < 0:
        raise ValueError("unterminated closing tag")
    return end + 1


def _opening_qname(xml: bytes, start: int, end: int) -> bytes:
    match = re.match(rb"<\s*([^\s/>]+)", xml[start:end])
    if match is None:
        raise ValueError("missing opening name")
    return match.group(1)


def _cells(index: WorksheetIndex) -> tuple[_CellSpan, ...]:
    return tuple(index.cells.values()) + index.cells_without_reference


def inspect_index_cell(
    index: WorksheetIndex, coordinate: str, error_code: str = "TARGET_CELL_MISSING"
) -> tuple[bytes, str | None, bool, bool, str | None]:
    element = index.cells.get(coordinate)
    if element is None or coordinate in index.duplicate_coordinates:
        detail = (
            f"duplicate XML cell {coordinate}"
            if coordinate in index.duplicate_coordinates
            else coordinate
        )
        raise ExcelWriterIntegrityError(error_code, detail)
    value = _child(element, "v", "TARGET_CELL_LEXEME_MISMATCH")
    if value is not None and value.has_children:
        raise ExcelWriterIntegrityError(error_code, coordinate)
    try:
        lexeme = (
            index.xml[value.content_start : value.content_end].decode("utf-8")
            if value is not None and not value.self_closing
            else None
        )
    except UnicodeDecodeError as error:
        raise ExcelWriterIntegrityError(error_code, coordinate) from error
    return (
        index.xml[element.start : element.end],
        lexeme,
        _child(element, "f", error_code) is not None,
        element.has_style,
        element.cell_type,
    )


def _child(
    element: _CellSpan, local_name: str, error_code: str = "TARGET_CELL_LEXEME_MISMATCH"
) -> _ChildSpan | None:
    child = element.formula if local_name == "f" else element.value
    duplicate = element.duplicate_formula if local_name == "f" else element.duplicate_value
    if duplicate:
        raise ExcelWriterIntegrityError(error_code, "ambiguous cell child")
    return child


def _value_qname(cell_qname: bytes) -> bytes:
    prefix, separator, _local_name = cell_qname.partition(b":")
    return prefix + separator + b"v" if separator else b"v"


def _remove_unqualified_type_attribute(cell: bytes) -> bytes:
    """Remove only the cell's plain `t` attribute, preserving all other lexemes."""

    opening_end = _opening_tag_end(cell, 0)
    opening = cell[:opening_end]
    index = _opening_qname(opening, 0, opening_end)
    cursor = opening.find(index) + len(index)
    while cursor < len(opening):
        whitespace_start = cursor
        while cursor < len(opening) and opening[cursor] in b" \t\r\n":
            cursor += 1
        if cursor >= len(opening) or opening[cursor : cursor + 1] in {b"/", b">"}:
            break
        name_start = cursor
        while cursor < len(opening) and opening[cursor] not in b" \t\r\n=>/":
            cursor += 1
        name = opening[name_start:cursor]
        while cursor < len(opening) and opening[cursor] in b" \t\r\n":
            cursor += 1
        if opening[cursor : cursor + 1] != b"=":
            break
        cursor += 1
        while cursor < len(opening) and opening[cursor] in b" \t\r\n":
            cursor += 1
        quote = opening[cursor : cursor + 1]
        if quote not in {b'"', b"'"}:
            break
        value_end = opening.find(quote, cursor + 1)
        if value_end < 0:
            break
        cursor = value_end + 1
        if name == b"t":
            return opening[:whitespace_start] + opening[cursor:] + cell[opening_end:]
    return cell


_CALC_CHAIN_RELATIONSHIP = re.compile(
    rb'<Relationship\b(?=[^>]*\bTarget\s*=\s*["\'](?:/?xl/)?calcChain\.xml["\'])[^>]*/>',
    re.IGNORECASE,
)


def reject_unsupported_package(source_path: Path) -> None:
    try:
        _preflight_zip(source_path, ExcelWriterSafetyError, "INVALID_XLSX_PACKAGE")
        with zipfile.ZipFile(source_path) as archive:
            admit_archive(archive, ExcelWriterSafetyError, "INVALID_XLSX_PACKAGE")
            if archive.testzip() is not None:
                raise ExcelWriterSafetyError("INVALID_XLSX_PACKAGE", "corrupt archive entry")
    except ExcelWriterSafetyError:
        raise
    except (OSError, zipfile.BadZipFile) as error:
        raise ExcelWriterSafetyError("INVALID_XLSX_PACKAGE", str(error)) from error


def admit_archive(archive: zipfile.ZipFile, error_type, code: str) -> None:
    """Validate central-directory metadata on this same archive handle before reads."""

    infos = tuple(archive.infolist())
    if len(infos) > _MAX_ARCHIVE_ENTRIES:
        raise error_type(code, "package admission failed")
    names: set[str] = set()
    total = 0
    for info in infos:
        if (
            info.filename in names
            or info.file_size < 0
            or info.compress_size < 0
            or info.flag_bits & 0b1_000_001
            or (info.file_size and not info.compress_size)
        ):
            raise error_type(code, "package admission failed")
        names.add(info.filename)
        if info.filename.casefold().startswith(("_xmlsignatures/", "xl/signatures/")):
            raise error_type("SIGNED_PACKAGE_UNSUPPORTED", "package admission failed")
        total += info.file_size
        if (
            info.file_size > _MAX_ARCHIVE_MEMBER_BYTES
            or total > _MAX_ARCHIVE_TOTAL_BYTES
            or info.file_size > info.compress_size * _MAX_COMPRESSION_RATIO
        ):
            raise error_type(code, "package admission failed")


def _validate_input_file_size(path: Path, error_type, code: str) -> None:
    if path.stat().st_size > _MAX_INPUT_FILE_BYTES:
        raise error_type(code, "package admission failed")


def _preflight_zip(path: Path, error_type, code: str) -> None:
    """Bound central-directory work before ``ZipFile`` allocates ``ZipInfo`` objects."""

    _validate_input_file_size(path, error_type, code)
    try:
        size = path.stat().st_size
        with path.open("rb") as stream:
            stream.seek(max(0, size - 65_557))
            tail = stream.read(65_557)
            index = tail.rfind(b"PK\x05\x06")
            if index < 0 or len(tail) - index < 22:
                raise ValueError("missing EOCD")
            record = struct.unpack_from("<4s4H2LH", tail, index)
            entries, directory_size, directory_offset = record[4:7]
            if entries == 0xFFFF or directory_size == 0xFFFFFFFF or directory_offset == 0xFFFFFFFF:
                locator = tail.rfind(b"PK\x06\x07", 0, index)
                if locator < 0 or index - locator < 20:
                    raise ValueError("missing ZIP64 locator")
                _, _, zip64_offset, _ = struct.unpack_from("<4sLQL", tail, locator)
                if zip64_offset < 0 or zip64_offset + 56 > size:
                    raise ValueError("invalid ZIP64 offset")
                stream.seek(zip64_offset)
                header = stream.read(56)
                values = struct.unpack("<4sQHHLLQQQQ", header)
                if values[0] != b"PK\x06\x06":
                    raise ValueError("invalid ZIP64 EOCD")
                entries, directory_size, directory_offset = values[7:10]
            if (
                entries > _MAX_ARCHIVE_ENTRIES
                or directory_size > _MAX_CENTRAL_DIRECTORY_BYTES
                or directory_offset + directory_size > size
            ):
                raise ValueError("central directory exceeds limit")
    except (OSError, ValueError, struct.error) as error:
        raise error_type(code, "package admission failed") from error


def validate_xlsx_source(path: Path, error_type, code: str) -> None:
    """Validate physical size and bounded ZIP metadata before any package access."""

    _preflight_zip(path, error_type, code)


def read_archive_part(archive: zipfile.ZipFile, name: str, error_type, code: str) -> bytes:
    """Read a previously admitted member, applying the worksheet-specific ceiling first."""

    try:
        info = archive.getinfo(name)
    except KeyError as error:
        raise error_type(code, "package member missing") from error
    if name.startswith("xl/worksheets/") and info.file_size > _MAX_WORKSHEET_XML_BYTES:
        raise error_type(code, "worksheet XML exceeds limit")
    return archive.read(info)


def worksheet_part_map(source_path: Path) -> dict[str, str]:
    try:
        _preflight_zip(source_path, ExcelWriterSafetyError, "INVALID_XLSX_PACKAGE")
        with zipfile.ZipFile(source_path, "r") as archive:
            admit_archive(archive, ExcelWriterSafetyError, "INVALID_XLSX_PACKAGE")
            workbook = ElementTree.fromstring(
                read_archive_part(
                    archive, "xl/workbook.xml", ExcelWriterSafetyError, "INVALID_XLSX_PACKAGE"
                )
            )
            relationships = ElementTree.fromstring(
                read_archive_part(
                    archive,
                    "xl/_rels/workbook.xml.rels",
                    ExcelWriterSafetyError,
                    "INVALID_XLSX_PACKAGE",
                )
            )
    except (OSError, zipfile.BadZipFile, KeyError, ValueError) as error:
        raise ExcelWriterSafetyError("INVALID_XLSX_PACKAGE", str(error)) from error
    targets = {
        item.attrib["Id"]: item.attrib["Target"]
        for item in relationships.findall(f"{{{_PKG_REL_NS}}}Relationship")
        if "Id" in item.attrib and "Target" in item.attrib
    }
    parts: dict[str, str] = {}
    sheets = workbook.find(f"{{{_SPREADSHEETML_NS}}}sheets")
    if sheets is None:
        return parts
    for sheet in sheets.findall(f"{{{_SPREADSHEETML_NS}}}sheet"):
        name = sheet.attrib.get("name")
        relation = sheet.attrib.get(f"{{{_REL_NS}}}id")
        target = targets.get(relation or "")
        if name and target:
            parts[name] = posixpath.normpath(posixpath.join("xl", target)).lstrip("/")
    return parts


def inspect_cell(xml: bytes, coordinate: str) -> tuple[bytes, str | None, bool, bool, str | None]:
    """Return target cell bytes, numeric lexeme, formula flag, and style presence."""

    return inspect_index_cell(worksheet_index(xml), coordinate)


def replace_cell_value(xml: bytes, coordinate: str, decimal_text: str) -> bytes:
    return _replace_cell_values(xml, ((coordinate, decimal_text),))


def _replace_cell_values(xml: bytes, changes: tuple[tuple[str, str], ...]) -> bytes:
    """Apply one worksheet part's requested replacements after one namespace scan."""

    return _replace_index_cell_values(worksheet_index(xml), changes)


def _replace_index_cell_values(
    index: WorksheetIndex, changes: tuple[tuple[str, str], ...]
) -> bytes:
    """Apply replacements using already-scanned immutable worksheet evidence."""

    requested = dict(changes)
    if len(requested) != len(changes):
        raise ExcelWriterIntegrityError("TARGET_CELL_MISSING", "duplicate requested cell")
    pieces: list[bytes] = []
    cursor = 0
    changed: set[str] = set()
    xml = index.xml
    for element in _cells(index):
        coordinate = element.coordinate
        if coordinate not in requested:
            continue
        if coordinate in changed:
            raise ExcelWriterIntegrityError(
                "TARGET_CELL_MISSING", f"duplicate XML cell {coordinate}"
            )
        replacement = requested[coordinate].encode("ascii")
        cell_type = element.cell_type
        if cell_type is not None and cell_type != "n":
            raise ExcelWriterIntegrityError("TARGET_CELL_LEXEME_MISMATCH", coordinate)
        cell = xml[element.start : element.end]
        value = _child(element, "v")
        if value is None:
            if not element.self_closing:
                raise ExcelWriterIntegrityError(
                    "TARGET_CELL_MISSING", f"missing value node {coordinate}"
                )
            opening = xml[element.start : element.opening_end]
            updated = (
                opening.rstrip()[:-2]
                + b"><"
                + _value_qname(element.qname)
                + b">"
                + replacement
                + b"</"
                + _value_qname(element.qname)
                + b"></"
                + element.qname
                + b">"
            )
        elif value.self_closing:
            opening = xml[value.start : value.opening_end]
            replacement_node = (
                opening.rstrip()[:-2] + b">" + replacement + b"</" + value.qname + b">"
            )
            updated = (
                cell[: value.start - element.start]
                + replacement_node
                + cell[value.end - element.start :]
            )
        else:
            updated = (
                cell[: value.content_start - element.start]
                + replacement
                + cell[value.content_end - element.start :]
            )
        pieces.extend((xml[cursor : element.start], updated))
        cursor = element.end
        changed.add(coordinate)
    if changed != set(requested):
        missing = next(iter(set(requested).difference(changed)))
        raise ExcelWriterIntegrityError("TARGET_CELL_MISSING", missing)
    pieces.append(xml[cursor:])
    return b"".join(pieces)


def formula_count(xml: bytes) -> int:
    """Return the number of formula elements in one worksheet part."""

    return worksheet_index(xml).formula_count


def formula_coordinates(xml: bytes) -> tuple[str, ...]:
    """Return formula coordinates from one authoritative worksheet XML part."""

    coordinates: list[str] = []
    for cell in _cells(worksheet_index(xml, "FORMULA_MATERIALIZATION_FAILED")):
        if _child(cell, "f", "FORMULA_MATERIALIZATION_FAILED") is None:
            continue
        reference = cell.coordinate
        if reference is None:
            raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", "formula without ref")
        coordinates.append(reference)
    if len(coordinates) != len(set(coordinates)):
        raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", "duplicate formula ref")
    return tuple(coordinates)


def numeric_formula_values(xml: bytes, coordinates: tuple[str, ...]) -> dict[str, str]:
    """Extract validated numeric values for requested coordinates from LibreOffice XML."""

    requested = set(coordinates)
    values: dict[str, str] = {}
    for cell in _cells(worksheet_index(xml, "FORMULA_RESULT_NOT_NUMERIC")):
        coordinate = cell.coordinate
        if coordinate is None:
            continue
        if coordinate not in requested:
            continue
        values[coordinate] = _finite_numeric_lexeme(xml, cell, coordinate)
    if set(values) != requested:
        missing = next(iter(requested.difference(values)), "unknown")
        raise ExcelWriterIntegrityError("FORMULA_RESULT_NOT_NUMERIC", missing)
    return values


def materialize_formula_cells(xml: bytes, values: Mapping[str, str]) -> bytes:
    """Replace authoritative worksheet formulas using LibreOffice numeric results."""

    pieces: list[bytes] = []
    cursor = 0
    for element in _cells(worksheet_index(xml, "FORMULA_MATERIALIZATION_FAILED")):
        formula = _child(element, "f", "FORMULA_MATERIALIZATION_FAILED")
        if formula is None:
            continue
        coordinate = element.coordinate
        if coordinate is None:
            raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", "formula without ref")
        decimal_text = values.get(coordinate)
        if decimal_text is None:
            raise ExcelWriterIntegrityError("FORMULA_RESULT_NOT_NUMERIC", coordinate)
        cell = xml[element.start : element.end]
        value = _child(element, "v", "FORMULA_MATERIALIZATION_FAILED")
        if value is None or value.has_children:
            raise ExcelWriterIntegrityError("FORMULA_RESULT_NOT_NUMERIC", coordinate)
        replacement = decimal_text.encode("ascii")
        if value.self_closing:
            value_start = value.start - element.start
            value_end = value.end - element.start
            opening = xml[value.start : value.opening_end]
            value_replacement = (
                opening.rstrip()[:-2] + b">" + replacement + b"</" + value.qname + b">"
            )
        else:
            value_start = value.content_start - element.start
            value_end = value.content_end - element.start
            value_replacement = replacement
        edits = sorted(
            (
                (formula.start - element.start, formula.end - element.start, b""),
                (value_start, value_end, value_replacement),
            ),
            reverse=True,
        )
        updated = cell
        for start, end, replacement_bytes in edits:
            updated = updated[:start] + replacement_bytes + updated[end:]
        updated = _remove_unqualified_type_attribute(updated)
        pieces.extend((xml[cursor : element.start], updated))
        cursor = element.end
    pieces.append(xml[cursor:])
    return b"".join(pieces)


def write_temp_package(
    source_path: Path,
    temp_path: Path,
    changes_by_part: Mapping[str, tuple[tuple[str, str], ...]],
    *,
    remove_calc_chain: bool = False,
) -> None:
    """Copy every archive part and replace only requested worksheet cell lexemes."""

    try:
        _preflight_zip(source_path, ExcelWriterAtomicError, "ATOMIC_PUBLISH_FAILED")
        with (
            zipfile.ZipFile(source_path, "r") as source,
            zipfile.ZipFile(temp_path, "w", allowZip64=True) as output,
        ):
            admit_archive(source, ExcelWriterAtomicError, "ATOMIC_PUBLISH_FAILED")
            output.comment = source.comment
            for info in source.infolist():
                if remove_calc_chain and info.filename == "xl/calcChain.xml":
                    continue
                payload = read_archive_part(
                    source, info.filename, ExcelWriterAtomicError, "ATOMIC_PUBLISH_FAILED"
                )
                changes = changes_by_part.get(info.filename, ())
                if changes:
                    payload = _replace_cell_values(payload, changes)
                if remove_calc_chain:
                    payload = _remove_calc_chain_metadata(info.filename, payload)
                output.writestr(info, payload)
    except (OSError, zipfile.BadZipFile, ValueError) as error:
        raise ExcelWriterAtomicError("ATOMIC_PUBLISH_FAILED", str(error)) from error
    _fsync_file(temp_path)


def verify_temp_package(
    source_path: Path,
    temp_path: Path,
    changes_by_part: Mapping[str, tuple[tuple[str, str], ...]],
    *,
    remove_calc_chain: bool = False,
) -> None:
    """Verify values and prove every unaffected part has the original bytes."""

    try:
        _preflight_zip(source_path, ExcelWriterIntegrityError, "PRESERVATION_CHECK_FAILED")
        _preflight_zip(temp_path, ExcelWriterIntegrityError, "PRESERVATION_CHECK_FAILED")
        with zipfile.ZipFile(source_path) as source, zipfile.ZipFile(temp_path) as output:
            admit_archive(source, ExcelWriterIntegrityError, "PRESERVATION_CHECK_FAILED")
            admit_archive(output, ExcelWriterIntegrityError, "PRESERVATION_CHECK_FAILED")
            source_names = tuple(source.namelist())
            expected_names = tuple(
                name for name in source_names if not remove_calc_chain or name != "xl/calcChain.xml"
            )
            if expected_names != tuple(output.namelist()) or output.testzip() is not None:
                raise ExcelWriterIntegrityError(
                    "PRESERVATION_CHECK_FAILED", "package structure changed"
                )
            source_indexes: dict[str, WorksheetIndex] = {}
            for name in source_names:
                if remove_calc_chain and name == "xl/calcChain.xml":
                    continue
                original = read_archive_part(
                    source, name, ExcelWriterIntegrityError, "PRESERVATION_CHECK_FAILED"
                )
                updated = read_archive_part(
                    output, name, ExcelWriterIntegrityError, "PRESERVATION_CHECK_FAILED"
                )
                expected = original
                changes = changes_by_part.get(name, ())
                if changes:
                    index = source_indexes.setdefault(
                        name, worksheet_index(original, "PRESERVATION_CHECK_FAILED")
                    )
                    expected = _replace_index_cell_values(index, changes)
                if remove_calc_chain:
                    expected = _remove_calc_chain_metadata(name, expected)
                if updated != expected:
                    raise ExcelWriterIntegrityError("PRESERVATION_CHECK_FAILED", name)
        with temp_path.open("rb") as stream:
            workbook = load_workbook(stream, read_only=True, data_only=False, keep_links=True)
            workbook.close()
    except ExcelWriterIntegrityError:
        raise
    except Exception as error:  # openpyxl exposes several parser exception types.
        raise ExcelWriterIntegrityError("REOPEN_FAILED", str(error)) from error


def materialize_formula_package(
    path: Path,
    worksheet_parts: Mapping[str, str],
    values_by_part: Mapping[str, Mapping[str, str]],
) -> None:
    """Materialize every formula in-place and remove obsolete calculation-chain metadata."""

    temporary = path.with_suffix(".materializing.xlsx")
    try:
        _preflight_zip(path, ExcelWriterIntegrityError, "FORMULA_MATERIALIZATION_FAILED")
        with (
            zipfile.ZipFile(path, "r") as source,
            zipfile.ZipFile(temporary, "w", allowZip64=True) as output,
        ):
            admit_archive(source, ExcelWriterIntegrityError, "FORMULA_MATERIALIZATION_FAILED")
            output.comment = source.comment
            for info in source.infolist():
                if info.filename == "xl/calcChain.xml":
                    continue
                payload = read_archive_part(
                    source,
                    info.filename,
                    ExcelWriterIntegrityError,
                    "FORMULA_MATERIALIZATION_FAILED",
                )
                if info.filename in worksheet_parts.values():
                    payload = materialize_formula_cells(
                        payload, values_by_part.get(info.filename, {})
                    )
                payload = _remove_calc_chain_metadata(info.filename, payload)
                output.writestr(info, payload)
        _fsync_file(temporary)
        os.replace(temporary, path)
        _fsync_file(path)
    except ExcelWriterIntegrityError:
        temporary.unlink(missing_ok=True)
        raise
    except (OSError, zipfile.BadZipFile, ValueError) as error:
        temporary.unlink(missing_ok=True)
        raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", str(error)) from error
    return None


def verify_materialized_package(
    path: Path, values_by_part: Mapping[str, Mapping[str, str]]
) -> None:
    """Prove that all worksheet formulas became the expected numeric values."""

    try:
        _preflight_zip(path, ExcelWriterIntegrityError, "FORMULA_MATERIALIZATION_FAILED")
        with zipfile.ZipFile(path) as package:
            admit_archive(package, ExcelWriterIntegrityError, "FORMULA_MATERIALIZATION_FAILED")
            names = tuple(package.namelist())
            if "xl/calcChain.xml" in names or package.testzip() is not None:
                raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", "calcChain")
            for part, values in values_by_part.items():
                xml = read_archive_part(
                    package, part, ExcelWriterIntegrityError, "FORMULA_MATERIALIZATION_FAILED"
                )
                if formula_count(xml):
                    raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", part)
                index = worksheet_index(xml, "FORMULA_MATERIALIZATION_FAILED")
                for coordinate, expected in values.items():
                    _, actual, is_formula, _, cell_type = inspect_index_cell(
                        index, coordinate, "FORMULA_MATERIALIZATION_FAILED"
                    )
                    if is_formula or cell_type not in {None, "n"} or actual != expected:
                        raise ExcelWriterIntegrityError(
                            "FORMULA_MATERIALIZATION_FAILED", coordinate
                        )
    except ExcelWriterIntegrityError:
        raise
    except (OSError, zipfile.BadZipFile, KeyError) as error:
        raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", str(error)) from error


def package_has_formulas(path: Path, worksheet_parts: Mapping[str, str]) -> bool:
    """Return whether any final worksheet still contains a formula element."""

    try:
        _preflight_zip(path, ExcelWriterIntegrityError, "FORMULA_MATERIALIZATION_FAILED")
        with zipfile.ZipFile(path) as package:
            admit_archive(package, ExcelWriterIntegrityError, "FORMULA_MATERIALIZATION_FAILED")
            return any(
                formula_count(
                    read_archive_part(
                        package, part, ExcelWriterIntegrityError, "FORMULA_MATERIALIZATION_FAILED"
                    )
                )
                for part in worksheet_parts.values()
            )
    except (OSError, zipfile.BadZipFile, KeyError) as error:
        raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", str(error)) from error


def verify_formula_free_package(path: Path, worksheet_parts: Mapping[str, str]) -> None:
    """Verify formula-free worksheets and the absence of stale calcChain metadata."""

    try:
        _preflight_zip(path, ExcelWriterIntegrityError, "FORMULA_MATERIALIZATION_FAILED")
        with zipfile.ZipFile(path) as package:
            admit_archive(package, ExcelWriterIntegrityError, "FORMULA_MATERIALIZATION_FAILED")
            names = tuple(package.namelist())
            if "xl/calcChain.xml" in names or package.testzip() is not None:
                raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", "calcChain")
            if any(
                formula_count(
                    read_archive_part(
                        package, part, ExcelWriterIntegrityError, "FORMULA_MATERIALIZATION_FAILED"
                    )
                )
                for part in worksheet_parts.values()
            ):
                raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", "formula remains")
    except ExcelWriterIntegrityError:
        raise
    except (OSError, zipfile.BadZipFile, KeyError) as error:
        raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", str(error)) from error


def _remove_calc_chain_metadata(name: str, payload: bytes) -> bytes:
    if name == "[Content_Types].xml":
        return _CALC_CHAIN_CONTENT_TYPE.sub(b"", payload)
    if name == "xl/_rels/workbook.xml.rels":
        return _CALC_CHAIN_RELATIONSHIP.sub(b"", payload)
    return payload


def _finite_numeric_lexeme(xml: bytes, cell: _CellSpan, coordinate: str) -> str:
    cell_type = cell.cell_type
    if cell_type is not None and cell_type != "n":
        raise ExcelWriterIntegrityError("FORMULA_RESULT_NOT_NUMERIC", coordinate)
    value = _child(cell, "v", "FORMULA_RESULT_NOT_NUMERIC")
    if value is None or value.self_closing or value.has_children:
        raise ExcelWriterIntegrityError("FORMULA_RESULT_NOT_NUMERIC", coordinate)
    try:
        decimal_text = xml[value.content_start : value.content_end].decode("ascii")
    except UnicodeDecodeError as error:
        raise ExcelWriterIntegrityError("FORMULA_RESULT_NOT_NUMERIC", coordinate) from error
    try:
        numeric = Decimal(decimal_text)
    except (InvalidOperation, ValueError) as error:
        raise ExcelWriterIntegrityError("FORMULA_RESULT_NOT_NUMERIC", coordinate) from error
    if not numeric.is_finite():
        raise ExcelWriterIntegrityError("FORMULA_RESULT_NOT_NUMERIC", coordinate)
    return decimal_text


def publish_no_clobber(temp_path: Path, output_path: Path) -> None:
    linked = False
    try:
        os.link(temp_path, output_path)
        linked = True
        temp_path.unlink()
        _fsync_directory(output_path.parent)
    except FileExistsError as error:
        temp_path.unlink(missing_ok=True)
        raise ExcelWriterSafetyError("OUTPUT_EXISTS", str(output_path)) from error
    except OSError as error:
        if linked:
            output_path.unlink(missing_ok=True)
        temp_path.unlink(missing_ok=True)
        raise ExcelWriterAtomicError("ATOMIC_PUBLISH_FAILED", str(error)) from error


def _fsync_file(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory(directory: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(directory, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
