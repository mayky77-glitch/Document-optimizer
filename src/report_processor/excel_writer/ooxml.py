"""Byte-preserving worksheet-cell changes for XLSX archives."""

from __future__ import annotations

import os
import re
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.parsers import expat

from openpyxl import load_workbook

from report_processor.target_report.ooxml import worksheet_parts

from .exceptions import ExcelWriterAtomicError, ExcelWriterIntegrityError, ExcelWriterSafetyError

_SPREADSHEETML_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_CALC_CHAIN_CONTENT_TYPE = re.compile(
    rb'<Override\b(?=[^>]*\bPartName\s*=\s*["\']/xl/calcChain\.xml["\'])[^>]*/>',
    re.IGNORECASE,
)


@dataclass
class _WorksheetElement:
    name: str
    qname: bytes
    attributes: dict[str, str]
    start: int
    opening_end: int
    end: int = 0
    content_start: int = 0
    content_end: int = 0
    self_closing: bool = False
    parent: _WorksheetElement | None = None
    children: list[_WorksheetElement] = field(default_factory=list)


class _RejectedWorksheetXml(Exception):
    """Internal sentinel for worksheet constructs that must never be expanded."""


def _worksheet_elements(
    xml: bytes, error_code: str = "TARGET_CELL_MISSING"
) -> tuple[_WorksheetElement, ...]:
    """Return namespace-expanded worksheet elements with their original byte spans.

    Expat resolves namespaces without touching ElementTree's process-global registry; the
    raw tag lexeme is recovered from Expat's byte index so edits retain its exact prefix.
    """

    parser = expat.ParserCreate(namespace_separator="}")
    elements: list[_WorksheetElement] = []
    stack: list[_WorksheetElement] = []

    def start(name: str, attributes: dict[str, str]) -> None:
        offset = parser.CurrentByteIndex
        opening_end = _opening_tag_end(xml, offset)
        qname = _opening_qname(xml, offset, opening_end)
        element = _WorksheetElement(
            name, qname, attributes, offset, opening_end, content_start=opening_end
        )
        if stack:
            element.parent = stack[-1]
            stack[-1].children.append(element)
        elements.append(element)
        stack.append(element)

    def end(_name: str) -> None:
        element = stack.pop()
        offset = parser.CurrentByteIndex
        element.self_closing = xml[element.start : element.opening_end].rstrip().endswith(b"/>")
        if element.self_closing:
            element.end = offset
            element.content_end = element.opening_end
        else:
            closing_end = _closing_tag_end(xml, offset)
            element.content_end = offset
            element.end = closing_end

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
    return tuple(elements)


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


def _is_sheet_element(element: _WorksheetElement, local_name: str) -> bool:
    return element.name == _SPREADSHEETML_NS + "}" + local_name


def _cells(xml: bytes, error_code: str = "TARGET_CELL_MISSING") -> tuple[_WorksheetElement, ...]:
    return tuple(
        item for item in _worksheet_elements(xml, error_code) if _is_sheet_element(item, "c")
    )


def _child(
    element: _WorksheetElement, local_name: str, error_code: str = "TARGET_CELL_LEXEME_MISMATCH"
) -> _WorksheetElement | None:
    matches = [item for item in element.children if _is_sheet_element(item, local_name)]
    if len(matches) > 1:
        raise ExcelWriterIntegrityError(error_code, "ambiguous cell child")
    return matches[0] if matches else None


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
        with zipfile.ZipFile(source_path) as archive:
            names = tuple(archive.namelist())
            if len(names) != len(set(names)):
                raise ExcelWriterSafetyError("INVALID_XLSX_PACKAGE", "duplicate package entries")
            if any(
                name.casefold().startswith(("_xmlsignatures/", "xl/signatures/")) for name in names
            ):
                raise ExcelWriterSafetyError(
                    "SIGNED_PACKAGE_UNSUPPORTED", "digital signatures cannot be preserved safely"
                )
            if archive.testzip() is not None:
                raise ExcelWriterSafetyError("INVALID_XLSX_PACKAGE", "corrupt archive entry")
    except ExcelWriterSafetyError:
        raise
    except (OSError, zipfile.BadZipFile) as error:
        raise ExcelWriterSafetyError("INVALID_XLSX_PACKAGE", str(error)) from error


def worksheet_part_map(source_path: Path) -> dict[str, str]:
    try:
        return worksheet_parts(source_path)
    except (OSError, zipfile.BadZipFile, KeyError, ValueError) as error:
        raise ExcelWriterSafetyError("INVALID_XLSX_PACKAGE", str(error)) from error


def inspect_cell(xml: bytes, coordinate: str) -> tuple[bytes, str | None, bool, bool, str | None]:
    """Return target cell bytes, numeric lexeme, formula flag, and style presence."""

    matches = [item for item in _cells(xml) if item.attributes.get("r") == coordinate]
    if len(matches) > 1:
        raise ExcelWriterIntegrityError("TARGET_CELL_MISSING", f"duplicate XML cell {coordinate}")
    if matches:
        element = matches[0]
        value = _child(element, "v")
        if value is not None and value.children:
            raise ExcelWriterIntegrityError("TARGET_CELL_LEXEME_MISMATCH", coordinate)
        lexeme = (
            xml[value.content_start : value.content_end].decode("utf-8")
            if value is not None and not value.self_closing
            else None
        )
        return (
            xml[element.start : element.end],
            lexeme,
            _child(element, "f") is not None,
            "s" in element.attributes,
            element.attributes.get("t"),
        )
    raise ExcelWriterIntegrityError("TARGET_CELL_MISSING", coordinate)


def replace_cell_value(xml: bytes, coordinate: str, decimal_text: str) -> bytes:
    return _replace_cell_values(xml, ((coordinate, decimal_text),))


def _replace_cell_values(xml: bytes, changes: tuple[tuple[str, str], ...]) -> bytes:
    """Apply one worksheet part's requested replacements after one namespace scan."""

    requested = dict(changes)
    if len(requested) != len(changes):
        raise ExcelWriterIntegrityError("TARGET_CELL_MISSING", "duplicate requested cell")
    pieces: list[bytes] = []
    cursor = 0
    changed: set[str] = set()
    for element in _cells(xml):
        coordinate = element.attributes.get("r")
        if coordinate not in requested:
            continue
        if coordinate in changed:
            raise ExcelWriterIntegrityError(
                "TARGET_CELL_MISSING", f"duplicate XML cell {coordinate}"
            )
        replacement = requested[coordinate].encode("ascii")
        cell_type = element.attributes.get("t")
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

    return sum(_is_sheet_element(item, "f") for item in _worksheet_elements(xml))


def formula_coordinates(xml: bytes) -> tuple[str, ...]:
    """Return formula coordinates from one authoritative worksheet XML part."""

    coordinates: list[str] = []
    for cell in _cells(xml, "FORMULA_MATERIALIZATION_FAILED"):
        if _child(cell, "f", "FORMULA_MATERIALIZATION_FAILED") is None:
            continue
        reference = cell.attributes.get("r")
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
    for cell in _cells(xml, "FORMULA_RESULT_NOT_NUMERIC"):
        coordinate = cell.attributes.get("r")
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
    for element in _cells(xml, "FORMULA_MATERIALIZATION_FAILED"):
        formula = _child(element, "f", "FORMULA_MATERIALIZATION_FAILED")
        if formula is None:
            continue
        coordinate = element.attributes.get("r")
        if coordinate is None:
            raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", "formula without ref")
        decimal_text = values.get(coordinate)
        if decimal_text is None:
            raise ExcelWriterIntegrityError("FORMULA_RESULT_NOT_NUMERIC", coordinate)
        cell = xml[element.start : element.end]
        value = _child(element, "v", "FORMULA_MATERIALIZATION_FAILED")
        if value is None or value.children:
            raise ExcelWriterIntegrityError("FORMULA_RESULT_NOT_NUMERIC", coordinate)
        replacement = decimal_text.encode("ascii")
        if value.self_closing:
            value_start = value.start - element.start
            value_end = value.end - element.start
            value_replacement = b"<" + value.qname + b">" + replacement + b"</" + value.qname + b">"
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
        with (
            zipfile.ZipFile(source_path, "r") as source,
            zipfile.ZipFile(temp_path, "w", allowZip64=True) as output,
        ):
            output.comment = source.comment
            for info in source.infolist():
                if remove_calc_chain and info.filename == "xl/calcChain.xml":
                    continue
                payload = source.read(info.filename)
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
        with zipfile.ZipFile(source_path) as source, zipfile.ZipFile(temp_path) as output:
            source_names = tuple(source.namelist())
            expected_names = tuple(
                name for name in source_names if not remove_calc_chain or name != "xl/calcChain.xml"
            )
            if expected_names != tuple(output.namelist()) or output.testzip() is not None:
                raise ExcelWriterIntegrityError(
                    "PRESERVATION_CHECK_FAILED", "package structure changed"
                )
            for name in source_names:
                if remove_calc_chain and name == "xl/calcChain.xml":
                    continue
                original = source.read(name)
                updated = output.read(name)
                expected = original
                changes = changes_by_part.get(name, ())
                if changes:
                    expected = _replace_cell_values(expected, changes)
                if remove_calc_chain:
                    expected = _remove_calc_chain_metadata(name, expected)
                if updated != expected:
                    raise ExcelWriterIntegrityError("PRESERVATION_CHECK_FAILED", name)
            for part, changes in changes_by_part.items():
                updated = output.read(part)
                for coordinate, decimal_text in changes:
                    _, actual, is_formula, _, cell_type = inspect_cell(updated, coordinate)
                    if is_formula or cell_type not in {None, "n"} or actual != decimal_text:
                        raise ExcelWriterIntegrityError("PRESERVATION_CHECK_FAILED", coordinate)
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
            zipfile.ZipFile(path, "r") as source,
            zipfile.ZipFile(temporary, "w", allowZip64=True) as output,
        ):
            output.comment = source.comment
            for info in source.infolist():
                if info.filename == "xl/calcChain.xml":
                    continue
                payload = source.read(info.filename)
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
        with zipfile.ZipFile(path) as package:
            names = tuple(package.namelist())
            if "xl/calcChain.xml" in names or package.testzip() is not None:
                raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", "calcChain")
            for part, values in values_by_part.items():
                xml = package.read(part)
                if formula_count(xml):
                    raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", part)
                for coordinate, expected in values.items():
                    _, actual, is_formula, _, cell_type = inspect_cell(xml, coordinate)
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
        with zipfile.ZipFile(path) as package:
            return any(formula_count(package.read(part)) for part in worksheet_parts.values())
    except (OSError, zipfile.BadZipFile, KeyError) as error:
        raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", str(error)) from error


def verify_formula_free_package(path: Path, worksheet_parts: Mapping[str, str]) -> None:
    """Verify formula-free worksheets and the absence of stale calcChain metadata."""

    try:
        with zipfile.ZipFile(path) as package:
            names = tuple(package.namelist())
            if "xl/calcChain.xml" in names or package.testzip() is not None:
                raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", "calcChain")
            if any(formula_count(package.read(part)) for part in worksheet_parts.values()):
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


def _finite_numeric_lexeme(xml: bytes, cell: _WorksheetElement, coordinate: str) -> str:
    cell_type = cell.attributes.get("t")
    if cell_type is not None and cell_type != "n":
        raise ExcelWriterIntegrityError("FORMULA_RESULT_NOT_NUMERIC", coordinate)
    value = _child(cell, "v", "FORMULA_RESULT_NOT_NUMERIC")
    if value is None or value.self_closing or value.children:
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
