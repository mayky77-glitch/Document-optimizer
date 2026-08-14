"""Byte-preserving worksheet-cell changes for XLSX archives."""

from __future__ import annotations

import os
import posixpath
import re
import stat
import struct
import zipfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
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
_UNSAFE_XML_DECLARATION = re.compile(rb"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)


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
    """One compact scalar record; offsets are unpacked only for requested cells."""

    packed: bytes


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
    formula_count: int
    has_unreferenced_formula: bool


_MISSING_OFFSET = 0xFFFFFFFF
_CELL_SPAN = struct.Struct("<9IH")
_CELL_SELF_CLOSING = 1
_FORMULA_SELF_CLOSING = 2
_FORMULA_CHILDREN = 4
_VALUE_SELF_CLOSING = 8
_VALUE_CHILDREN = 16
_DUPLICATE_FORMULA = 32
_DUPLICATE_VALUE = 64
_HAS_STYLE = 128
_TYPE_NUMERIC = 256
_TYPE_OTHER = 512


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
    has_unreferenced_formula = False
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
            # A SpreadsheetML cell is valid for this writer only in the normal
            # worksheet/sheetData/row/c hierarchy.  Looking merely at the local
            # name would let a lookalike cell change writer evidence.
            if (
                not stack
                or stack[0][0] != _SPREADSHEETML_NS + "}worksheet"
                or [item[0] for item in stack[1:]]
                != [
                    _SPREADSHEETML_NS + "}sheetData",
                    _SPREADSHEETML_NS + "}row",
                ]
            ):
                raise _RejectedWorksheetXml()
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
        nonlocal has_unreferenced_formula, open_cells
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
            end = offset if self_closing else _closing_tag_end(xml, offset)
            flags = (
                (_CELL_SELF_CLOSING if self_closing else 0)
                | (_DUPLICATE_FORMULA if opened.duplicate_formula else 0)
                | (_DUPLICATE_VALUE if opened.duplicate_value else 0)
                | (_HAS_STYLE if opened.has_style else 0)
                | (_TYPE_NUMERIC if opened.cell_type == "n" else 0)
                | (_TYPE_OTHER if opened.cell_type not in {None, "n"} else 0)
            )
            formula = opened.formula
            value = opened.value
            if formula is not None:
                flags |= _FORMULA_SELF_CLOSING if formula.self_closing else 0
                flags |= _FORMULA_CHILDREN if formula.has_children else 0
            if value is not None:
                flags |= _VALUE_SELF_CLOSING if value.self_closing else 0
                flags |= _VALUE_CHILDREN if value.has_children else 0
            cell = _CellSpan(
                _CELL_SPAN.pack(
                    opened.start,
                    opened.opening_end,
                    end,
                    formula.start if formula is not None else _MISSING_OFFSET,
                    formula.opening_end if formula is not None else _MISSING_OFFSET,
                    formula.end if formula is not None else _MISSING_OFFSET,
                    value.start if value is not None else _MISSING_OFFSET,
                    value.opening_end if value is not None else _MISSING_OFFSET,
                    value.end if value is not None else _MISSING_OFFSET,
                    flags,
                )
            )
            reference = opened.coordinate
            if reference is not None:
                if reference in cells:
                    duplicate_coordinates.add(reference)
                else:
                    cells[reference] = cell
            elif formula is not None:
                has_unreferenced_formula = True

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
        formula_count,
        has_unreferenced_formula,
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


def _cell_fields(cell: _CellSpan) -> tuple[int, int, int, int, int, int, int, int, int, int]:
    return _CELL_SPAN.unpack(cell.packed)


def _cell_qname(index: WorksheetIndex, cell: _CellSpan) -> bytes:
    start, opening_end, *_rest = _cell_fields(cell)
    return _opening_qname(index.xml, start, opening_end)


def _cell_type(flags: int) -> str | None:
    if flags & _TYPE_NUMERIC:
        return "n"
    return "other" if flags & _TYPE_OTHER else None


def _child(
    index: WorksheetIndex,
    element: _CellSpan,
    local_name: str,
    error_code: str = "TARGET_CELL_LEXEME_MISMATCH",
) -> _ChildSpan | None:
    (
        _cell_start,
        _cell_opening_end,
        _cell_end,
        formula_start,
        formula_opening_end,
        formula_end,
        value_start,
        value_opening_end,
        value_end,
        flags,
    ) = _cell_fields(element)
    if local_name == "f":
        if flags & _DUPLICATE_FORMULA:
            raise ExcelWriterIntegrityError(error_code, "ambiguous cell child")
        start, opening_end, end = formula_start, formula_opening_end, formula_end
        self_closing = bool(flags & _FORMULA_SELF_CLOSING)
        has_children = bool(flags & _FORMULA_CHILDREN)
    else:
        if flags & _DUPLICATE_VALUE:
            raise ExcelWriterIntegrityError(error_code, "ambiguous cell child")
        start, opening_end, end = value_start, value_opening_end, value_end
        self_closing = bool(flags & _VALUE_SELF_CLOSING)
        has_children = bool(flags & _VALUE_CHILDREN)
    if start == _MISSING_OFFSET:
        return None
    return _ChildSpan(
        _opening_qname(index.xml, start, opening_end),
        start,
        opening_end,
        end,
        opening_end,
        opening_end if self_closing else _closing_start(index.xml, end),
        self_closing,
        has_children,
    )


def _require_unambiguous_cell(index: WorksheetIndex, coordinate: str, error_code: str) -> _CellSpan:
    element = index.cells.get(coordinate)
    if element is None or coordinate in index.duplicate_coordinates:
        raise ExcelWriterIntegrityError(error_code, "ambiguous worksheet cell")
    if _cell_fields(element)[-1] & (_DUPLICATE_FORMULA | _DUPLICATE_VALUE):
        raise ExcelWriterIntegrityError(error_code, "ambiguous worksheet cell")
    return element


def _closing_start(xml: bytes, end: int) -> int:
    start = xml.rfind(b"<", 0, end)
    if start < 0:
        raise ValueError("missing closing tag")
    return start


def inspect_index_cell(
    index: WorksheetIndex, coordinate: str, error_code: str = "TARGET_CELL_MISSING"
) -> tuple[bytes, str | None, bool, bool, str | None]:
    element = _require_unambiguous_cell(index, coordinate, error_code)
    value = _child(index, element, "v", error_code)
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
        index.xml[_cell_fields(element)[0] : _cell_fields(element)[2]],
        lexeme,
        _child(index, element, "f", error_code) is not None,
        bool(_cell_fields(element)[-1] & _HAS_STYLE),
        _cell_type(_cell_fields(element)[-1]),
    )


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
        with admitted_zipfile(
            source_path, ExcelWriterSafetyError, "INVALID_XLSX_PACKAGE"
        ) as archive:
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


@contextmanager
def admitted_zipfile(path: Path | int, error_type, code: str) -> Iterator[zipfile.ZipFile]:
    """Open one no-follow descriptor, preflight it, and consume that exact inode."""
    descriptor = -1
    stream = None
    archive = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.dup(path) if isinstance(path, int) else os.open(path, flags)
        _preflight_zip_descriptor(descriptor)
        stream = os.fdopen(os.dup(descriptor), "rb")
        archive = zipfile.ZipFile(stream, "r")
        admit_archive(archive, error_type, code)
        yield archive
    except (ExcelWriterAtomicError, ExcelWriterIntegrityError, ExcelWriterSafetyError):
        raise
    except (OSError, ValueError, struct.error, zipfile.BadZipFile) as error:
        raise error_type(code, "package admission failed") from error
    finally:
        if archive is not None:
            archive.close()
        if stream is not None:
            stream.close()
        if descriptor >= 0:
            os.close(descriptor)


def _preflight_zip(path: Path, error_type, code: str) -> None:
    """Bound central-directory work before ``ZipFile`` allocates ``ZipInfo`` objects."""

    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        try:
            _preflight_zip_descriptor(descriptor)
        finally:
            os.close(descriptor)
    except (OSError, ValueError, struct.error) as error:
        raise error_type(code, "package admission failed") from error


def _preflight_zip_descriptor(descriptor: int) -> None:
    """Raw EOCD/ZIP64 admission on an already-open regular-file descriptor."""
    details = os.fstat(descriptor)
    if not stat.S_ISREG(details.st_mode) or details.st_size > _MAX_INPUT_FILE_BYTES:
        raise ValueError("invalid package file")
    size = details.st_size
    stream = os.fdopen(os.dup(descriptor), "rb")
    try:
        stream.seek(max(0, size - 65_557))
        tail = stream.read(65_557)
        index = _eocd_index(tail)
        if index is None:
            raise ValueError("missing EOCD")
        record = struct.unpack_from("<4s4H2LH", tail, index)
        (
            disk,
            directory_disk,
            entries_on_disk,
            entries,
            directory_size,
            directory_offset,
            _comment_length,
        ) = record[1:]
        if disk or directory_disk or entries_on_disk != entries:
            raise ValueError("multi-disk ZIP")
        eocd_offset = size - len(tail) + index
        central_end = eocd_offset
        if entries == 0xFFFF or directory_size == 0xFFFFFFFF or directory_offset == 0xFFFFFFFF:
            locator = eocd_offset - 20
            if locator < 0:
                raise ValueError("missing ZIP64 locator")
            stream.seek(locator)
            locator_record = _read_exact(stream, 20)
            signature, _disk, zip64_offset, total_disks = struct.unpack("<4sLQL", locator_record)
            if signature != b"PK\x06\x07" or total_disks != 1:
                raise ValueError("invalid ZIP64 locator")
            if zip64_offset < 0 or zip64_offset + 56 > size:
                raise ValueError("invalid ZIP64 offset")
            stream.seek(zip64_offset)
            header = _read_exact(stream, 56)
            values = struct.unpack("<4sQHHLLQQQQ", header)
            if (
                values[0] != b"PK\x06\x06"
                or values[1] < 44
                or zip64_offset + 12 + values[1] != locator
                or values[4]
                or values[5]
                or values[6] != values[7]
            ):
                raise ValueError("invalid ZIP64 EOCD")
            entries, directory_size, directory_offset = values[7:10]
            central_end = zip64_offset
        if (
            entries > _MAX_ARCHIVE_ENTRIES
            or directory_size > _MAX_CENTRAL_DIRECTORY_BYTES
            or directory_offset + directory_size != central_end
        ):
            raise ValueError("central directory exceeds limit")
        stream.seek(directory_offset)
        directory = _read_exact(stream, directory_size)
        _validate_raw_central_directory(directory, entries)
    finally:
        stream.close()


def _eocd_index(tail: bytes) -> int | None:
    """Find only an EOCD whose declared comment reaches the physical EOF."""

    cursor = len(tail)
    while (index := tail.rfind(b"PK\x05\x06", 0, cursor)) >= 0:
        if index + 22 <= len(tail):
            comment_length = struct.unpack_from("<H", tail, index + 20)[0]
            if index + 22 + comment_length == len(tail):
                return index
        cursor = index
    return None


def _read_exact(stream, size: int) -> bytes:
    payload = stream.read(size)
    if len(payload) != size:
        raise ValueError("truncated ZIP record")
    return payload


def _validate_raw_central_directory(directory: bytes, declared_entries: int) -> None:
    """Validate raw records before ``ZipFile`` can allocate attacker-controlled metadata."""

    cursor = 0
    count = 0
    while cursor < len(directory):
        if len(directory) - cursor < 46:
            raise ValueError("truncated central directory")
        fields = struct.unpack_from("<4s6H3I5H2I", directory, cursor)
        if fields[0] != b"PK\x01\x02":
            raise ValueError("invalid central-directory signature")
        name_length, extra_length, comment_length, disk_start = fields[10:14]
        record_size = 46 + name_length + extra_length + comment_length
        if disk_start:
            raise ValueError("multi-disk central directory")
        if record_size > len(directory) - cursor:
            raise ValueError("truncated central-directory record")
        cursor += record_size
        count += 1
        if count > _MAX_ARCHIVE_ENTRIES:
            raise ValueError("central directory has too many entries")
    if cursor != len(directory) or count != declared_entries:
        raise ValueError("central-directory count mismatch")


def validate_xlsx_source(path: Path, error_type, code: str) -> None:
    """Validate physical size and bounded ZIP metadata before any package access."""

    _preflight_zip(path, error_type, code)


def read_archive_part(
    archive: zipfile.ZipFile, name: str, error_type, code: str, *, worksheet: bool = False
) -> bytes:
    """Read a previously admitted member, applying the worksheet-specific ceiling first."""

    try:
        info = archive.getinfo(name)
    except KeyError as error:
        raise error_type(code, "package member missing") from error
    if worksheet and info.file_size > _MAX_WORKSHEET_XML_BYTES:
        raise error_type(code, "worksheet XML exceeds limit")
    return archive.read(info)


def worksheet_part_map(source_path: Path | int) -> dict[str, str]:
    try:
        with admitted_zipfile(
            source_path, ExcelWriterSafetyError, "INVALID_XLSX_PACKAGE"
        ) as archive:
            workbook = _safe_xml_root(
                read_archive_part(
                    archive, "xl/workbook.xml", ExcelWriterSafetyError, "INVALID_XLSX_PACKAGE"
                ),
                ExcelWriterSafetyError,
                "INVALID_XLSX_PACKAGE",
            )
            relationships = _safe_xml_root(
                read_archive_part(
                    archive,
                    "xl/_rels/workbook.xml.rels",
                    ExcelWriterSafetyError,
                    "INVALID_XLSX_PACKAGE",
                ),
                ExcelWriterSafetyError,
                "INVALID_XLSX_PACKAGE",
            )
    except (OSError, zipfile.BadZipFile, KeyError, ValueError) as error:
        raise ExcelWriterSafetyError("INVALID_XLSX_PACKAGE", "package metadata invalid") from error
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


def _safe_xml_root(payload: bytes, error_type, code: str) -> ElementTree.Element:
    """Reject entity-bearing metadata before a semantic XML parser observes it."""
    if _UNSAFE_XML_DECLARATION.search(payload):
        raise error_type(code, "package metadata invalid")
    parser = expat.ParserCreate(namespace_separator="}")
    depth = 0
    events = 0

    def start(_name: str, _attributes: dict[str, str]) -> None:
        nonlocal depth, events
        depth += 1
        events += 1
        if depth > _MAX_XML_DEPTH or events > _MAX_WORKSHEET_EVENTS:
            raise _RejectedWorksheetXml()

    def end(_name: str) -> None:
        nonlocal depth, events
        depth -= 1
        events += 1
        if depth < 0 or events > _MAX_WORKSHEET_EVENTS:
            raise _RejectedWorksheetXml()

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.StartDoctypeDeclHandler = lambda *_args: (_ for _ in ()).throw(_RejectedWorksheetXml())
    parser.EntityDeclHandler = lambda *_args: (_ for _ in ()).throw(_RejectedWorksheetXml())
    try:
        parser.Parse(payload, True)
        return ElementTree.fromstring(payload)
    except (
        ElementTree.ParseError,
        UnicodeDecodeError,
        ValueError,
        expat.ExpatError,
        _RejectedWorksheetXml,
    ) as error:
        raise error_type(code, "package metadata invalid") from error


def inspect_cell(xml: bytes, coordinate: str) -> tuple[bytes, str | None, bool, bool, str | None]:
    """Return target cell bytes, numeric lexeme, formula flag, and style presence."""

    return inspect_index_cell(worksheet_index(xml), coordinate)


def replace_cell_value(xml: bytes, coordinate: str, decimal_text: str) -> bytes:
    return _replace_cell_values(xml, ((coordinate, decimal_text),))


def _replace_cell_values(xml: bytes, changes: tuple[tuple[str, str], ...]) -> bytes:
    """Apply one worksheet part's requested replacements after one namespace scan."""

    return _replace_index_cell_values(worksheet_index(xml), changes)


def _replace_index_cell_values(
    index: WorksheetIndex,
    changes: tuple[tuple[str, str], ...],
    error_code: str = "TARGET_CELL_MISSING",
) -> bytes:
    """Apply replacements using already-scanned immutable worksheet evidence."""

    requested = dict(changes)
    if len(requested) != len(changes):
        raise ExcelWriterIntegrityError(error_code, "duplicate requested cell")
    for coordinate in requested:
        _require_unambiguous_cell(index, coordinate, error_code)
    pieces: list[bytes] = []
    cursor = 0
    changed: set[str] = set()
    xml = index.xml
    for coordinate, element in index.cells.items():
        if coordinate not in requested:
            continue
        if coordinate in changed:
            raise ExcelWriterIntegrityError(error_code, f"duplicate XML cell {coordinate}")
        replacement = requested[coordinate].encode("ascii")
        start, opening_end, end, *_unused, flags = _cell_fields(element)
        cell_type = _cell_type(flags)
        if cell_type is not None and cell_type != "n":
            raise ExcelWriterIntegrityError(error_code, coordinate)
        cell = xml[start:end]
        value = _child(index, element, "v", error_code)
        if value is None:
            if not flags & _CELL_SELF_CLOSING:
                raise ExcelWriterIntegrityError(error_code, f"missing value node {coordinate}")
            opening = xml[start:opening_end]
            qname = _cell_qname(index, element)
            updated = (
                opening.rstrip()[:-2]
                + b"><"
                + _value_qname(qname)
                + b">"
                + replacement
                + b"</"
                + _value_qname(qname)
                + b"></"
                + qname
                + b">"
            )
        elif value.self_closing:
            opening = xml[value.start : value.opening_end]
            replacement_node = (
                opening.rstrip()[:-2] + b">" + replacement + b"</" + value.qname + b">"
            )
            updated = cell[: value.start - start] + replacement_node + cell[value.end - start :]
        else:
            updated = (
                cell[: value.content_start - start]
                + replacement
                + cell[value.content_end - start :]
            )
        pieces.extend((xml[cursor:start], updated))
        cursor = end
        changed.add(coordinate)
    if changed != set(requested):
        missing = next(iter(set(requested).difference(changed)))
        raise ExcelWriterIntegrityError(error_code, missing)
    pieces.append(xml[cursor:])
    return b"".join(pieces)


def formula_count(xml: bytes) -> int:
    """Return the number of formula elements in one worksheet part."""

    return worksheet_index(xml).formula_count


def formula_coordinates(xml: bytes) -> tuple[str, ...]:
    """Return formula coordinates from one authoritative worksheet XML part."""

    coordinates: list[str] = []
    index = worksheet_index(xml, "FORMULA_MATERIALIZATION_FAILED")
    if index.has_unreferenced_formula:
        raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", "formula without ref")
    if index.duplicate_coordinates:
        raise ExcelWriterIntegrityError(
            "FORMULA_MATERIALIZATION_FAILED", "ambiguous worksheet cell"
        )
    for reference, cell in index.cells.items():
        _require_unambiguous_cell(index, reference, "FORMULA_MATERIALIZATION_FAILED")
        if _child(index, cell, "f", "FORMULA_MATERIALIZATION_FAILED") is None:
            continue
        coordinates.append(reference)
    if len(coordinates) != len(set(coordinates)):
        raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", "duplicate formula ref")
    return tuple(coordinates)


def numeric_formula_values(xml: bytes, coordinates: tuple[str, ...]) -> dict[str, str]:
    """Extract validated numeric values for requested coordinates from LibreOffice XML."""

    requested = set(coordinates)
    values: dict[str, str] = {}
    index = worksheet_index(xml, "FORMULA_RESULT_NOT_NUMERIC")
    for coordinate in requested:
        _require_unambiguous_cell(index, coordinate, "FORMULA_RESULT_NOT_NUMERIC")
    for coordinate, cell in index.cells.items():
        if coordinate not in requested:
            continue
        values[coordinate] = _finite_numeric_lexeme(index, cell, coordinate)
    if set(values) != requested:
        missing = next(iter(requested.difference(values)), "unknown")
        raise ExcelWriterIntegrityError("FORMULA_RESULT_NOT_NUMERIC", missing)
    return values


def materialize_formula_cells(xml: bytes, values: Mapping[str, str]) -> bytes:
    """Replace authoritative worksheet formulas using LibreOffice numeric results."""

    pieces: list[bytes] = []
    cursor = 0
    index = worksheet_index(xml, "FORMULA_MATERIALIZATION_FAILED")
    if index.has_unreferenced_formula:
        raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", "formula without ref")
    if index.duplicate_coordinates:
        raise ExcelWriterIntegrityError(
            "FORMULA_MATERIALIZATION_FAILED", "ambiguous worksheet cell"
        )
    for coordinate, element in index.cells.items():
        _require_unambiguous_cell(index, coordinate, "FORMULA_MATERIALIZATION_FAILED")
        formula = _child(index, element, "f", "FORMULA_MATERIALIZATION_FAILED")
        if formula is None:
            continue
        decimal_text = values.get(coordinate)
        if decimal_text is None:
            raise ExcelWriterIntegrityError("FORMULA_RESULT_NOT_NUMERIC", coordinate)
        start, _opening_end, end, *_rest = _cell_fields(element)
        cell = xml[start:end]
        value = _child(index, element, "v", "FORMULA_MATERIALIZATION_FAILED")
        if value is None or value.has_children:
            raise ExcelWriterIntegrityError("FORMULA_RESULT_NOT_NUMERIC", coordinate)
        replacement = decimal_text.encode("ascii")
        if value.self_closing:
            value_start = value.start - start
            value_end = value.end - start
            opening = xml[value.start : value.opening_end]
            value_replacement = (
                opening.rstrip()[:-2] + b">" + replacement + b"</" + value.qname + b">"
            )
        else:
            value_start = value.content_start - start
            value_end = value.content_end - start
            value_replacement = replacement
        edits = sorted(
            (
                (formula.start - start, formula.end - start, b""),
                (value_start, value_end, value_replacement),
            ),
            reverse=True,
        )
        updated = cell
        for edit_start, edit_end, replacement_bytes in edits:
            updated = updated[:edit_start] + replacement_bytes + updated[edit_end:]
        updated = _remove_unqualified_type_attribute(updated)
        pieces.extend((xml[cursor:start], updated))
        cursor = end
    pieces.append(xml[cursor:])
    return b"".join(pieces)


def write_temp_package(
    source_path: Path,
    temp_path: Path,
    changes_by_part: Mapping[str, tuple[tuple[str, str], ...]],
    *,
    remove_calc_chain: bool = False,
    worksheet_parts: frozenset[str] = frozenset(),
) -> None:
    """Copy every archive part and replace only requested worksheet cell lexemes."""

    try:
        with (
            admitted_zipfile(
                source_path, ExcelWriterAtomicError, "ATOMIC_PUBLISH_FAILED"
            ) as source,
            zipfile.ZipFile(temp_path, "w", allowZip64=True) as output,
        ):
            output.comment = source.comment
            for info in source.infolist():
                if remove_calc_chain and info.filename == "xl/calcChain.xml":
                    continue
                payload = read_archive_part(
                    source,
                    info.filename,
                    ExcelWriterAtomicError,
                    "ATOMIC_PUBLISH_FAILED",
                    worksheet=info.filename in worksheet_parts,
                )
                changes = changes_by_part.get(info.filename, ())
                if changes:
                    payload = _replace_index_cell_values(
                        worksheet_index(payload, "ATOMIC_PUBLISH_FAILED"),
                        changes,
                        "ATOMIC_PUBLISH_FAILED",
                    )
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
    worksheet_parts: frozenset[str] = frozenset(),
) -> None:
    """Verify values and prove every unaffected part has the original bytes."""

    try:
        with (
            admitted_zipfile(
                source_path, ExcelWriterIntegrityError, "PRESERVATION_CHECK_FAILED"
            ) as source,
            admitted_zipfile(
                temp_path, ExcelWriterIntegrityError, "PRESERVATION_CHECK_FAILED"
            ) as output,
        ):
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
                    source,
                    name,
                    ExcelWriterIntegrityError,
                    "PRESERVATION_CHECK_FAILED",
                    worksheet=name in worksheet_parts,
                )
                updated = read_archive_part(
                    output,
                    name,
                    ExcelWriterIntegrityError,
                    "PRESERVATION_CHECK_FAILED",
                    worksheet=name in worksheet_parts,
                )
                expected = original
                changes = changes_by_part.get(name, ())
                if changes:
                    index = source_indexes.setdefault(
                        name, worksheet_index(original, "PRESERVATION_CHECK_FAILED")
                    )
                    expected = _replace_index_cell_values(
                        index, changes, "PRESERVATION_CHECK_FAILED"
                    )
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
        with (
            admitted_zipfile(
                path, ExcelWriterIntegrityError, "FORMULA_MATERIALIZATION_FAILED"
            ) as source,
            zipfile.ZipFile(temporary, "w", allowZip64=True) as output,
        ):
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
        with admitted_zipfile(
            path, ExcelWriterIntegrityError, "FORMULA_MATERIALIZATION_FAILED"
        ) as package:
            names = tuple(package.namelist())
            if "xl/calcChain.xml" in names or package.testzip() is not None:
                raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", "calcChain")
            for part, values in values_by_part.items():
                xml = read_archive_part(
                    package,
                    part,
                    ExcelWriterIntegrityError,
                    "FORMULA_MATERIALIZATION_FAILED",
                    worksheet=True,
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
        with admitted_zipfile(
            path, ExcelWriterIntegrityError, "FORMULA_MATERIALIZATION_FAILED"
        ) as package:
            return any(
                formula_count(
                    read_archive_part(
                        package,
                        part,
                        ExcelWriterIntegrityError,
                        "FORMULA_MATERIALIZATION_FAILED",
                        worksheet=True,
                    )
                )
                for part in worksheet_parts.values()
            )
    except (OSError, zipfile.BadZipFile, KeyError) as error:
        raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", str(error)) from error


def verify_formula_free_package(path: Path, worksheet_parts: Mapping[str, str]) -> None:
    """Verify formula-free worksheets and the absence of stale calcChain metadata."""

    try:
        with admitted_zipfile(
            path, ExcelWriterIntegrityError, "FORMULA_MATERIALIZATION_FAILED"
        ) as package:
            names = tuple(package.namelist())
            if "xl/calcChain.xml" in names or package.testzip() is not None:
                raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", "calcChain")
            if any(
                formula_count(
                    read_archive_part(
                        package,
                        part,
                        ExcelWriterIntegrityError,
                        "FORMULA_MATERIALIZATION_FAILED",
                        worksheet=True,
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


def _finite_numeric_lexeme(index: WorksheetIndex, cell: _CellSpan, coordinate: str) -> str:
    cell_type = _cell_type(_cell_fields(cell)[-1])
    if cell_type is not None and cell_type != "n":
        raise ExcelWriterIntegrityError("FORMULA_RESULT_NOT_NUMERIC", coordinate)
    value = _child(index, cell, "v", "FORMULA_RESULT_NOT_NUMERIC")
    if value is None or value.self_closing or value.has_children:
        raise ExcelWriterIntegrityError("FORMULA_RESULT_NOT_NUMERIC", coordinate)
    try:
        decimal_text = index.xml[value.content_start : value.content_end].decode("ascii")
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
