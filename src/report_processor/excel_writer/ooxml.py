"""Byte-preserving worksheet-cell changes for XLSX archives."""

from __future__ import annotations

import os
import re
import zipfile
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openpyxl import load_workbook

from report_processor.target_report.ooxml import worksheet_parts

from .exceptions import ExcelWriterAtomicError, ExcelWriterIntegrityError, ExcelWriterSafetyError

_CELL = re.compile(rb"<c\b[^>]*(?:/>|>.*?</c>)", re.DOTALL)
_REFERENCE = re.compile(rb"\br\s*=\s*([\"'])([^\"']+)\1")
_STYLE = re.compile(rb"\bs\s*=\s*([\"'])([^\"']+)\1")
_TYPE = re.compile(rb"\bt\s*=\s*([\"'])([^\"']+)\1")
_FORMULA = re.compile(rb"<f\b[^>]*?(?:/>|>.*?</f>)", re.DOTALL)
_VALUE = re.compile(rb"<v(?:\s[^>]*)?(?:/>|>(.*?)</v>)", re.DOTALL)
_SELF_CLOSING = re.compile(rb"/>$")
_CALC_CHAIN_CONTENT_TYPE = re.compile(
    rb'<Override\b(?=[^>]*\bPartName\s*=\s*["\']/xl/calcChain\.xml["\'])[^>]*/>',
    re.IGNORECASE,
)
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

    coordinate_bytes = coordinate.encode("ascii")
    for match in _CELL.finditer(xml):
        cell = match.group(0)
        reference = _REFERENCE.search(cell)
        if reference is None or reference.group(2) != coordinate_bytes:
            continue
        value = _VALUE.search(cell)
        lexeme = value.group(1).decode("utf-8") if value and value.group(1) is not None else None
        cell_type = _TYPE.search(cell)
        return (
            cell,
            lexeme,
            _FORMULA.search(cell) is not None,
            _STYLE.search(cell) is not None,
            cell_type.group(2).decode("ascii") if cell_type is not None else None,
        )
    raise ExcelWriterIntegrityError("TARGET_CELL_MISSING", coordinate)


def replace_cell_value(xml: bytes, coordinate: str, decimal_text: str) -> bytes:
    coordinate_bytes = coordinate.encode("ascii")
    replacement = decimal_text.encode("ascii")
    pieces: list[bytes] = []
    cursor = 0
    changed = False
    for match in _CELL.finditer(xml):
        cell = match.group(0)
        reference = _REFERENCE.search(cell)
        if reference is None or reference.group(2) != coordinate_bytes:
            continue
        if changed:
            raise ExcelWriterIntegrityError(
                "TARGET_CELL_MISSING", f"duplicate XML cell {coordinate}"
            )
        cell_type = _TYPE.search(cell)
        if cell_type is not None and cell_type.group(2) not in {b"n"}:
            raise ExcelWriterIntegrityError("TARGET_CELL_LEXEME_MISMATCH", coordinate)
        value = _VALUE.search(cell)
        if value is None:
            if not _SELF_CLOSING.search(cell):
                raise ExcelWriterIntegrityError(
                    "TARGET_CELL_MISSING", f"missing value node {coordinate}"
                )
            updated = cell[:-2] + b"><v>" + replacement + b"</v></c>"
        elif value.group(1) is None:
            updated = cell[: value.start()] + b"<v>" + replacement + b"</v>" + cell[value.end() :]
        else:
            updated = cell[: value.start(1)] + replacement + cell[value.end(1) :]
        pieces.extend((xml[cursor : match.start()], updated))
        cursor = match.end()
        changed = True
    if not changed:
        raise ExcelWriterIntegrityError("TARGET_CELL_MISSING", coordinate)
    pieces.append(xml[cursor:])
    return b"".join(pieces)


def formula_count(xml: bytes) -> int:
    """Return the number of formula elements in one worksheet part."""

    return len(_FORMULA.findall(xml))


def formula_coordinates(xml: bytes) -> tuple[str, ...]:
    """Return formula coordinates from one authoritative worksheet XML part."""

    coordinates: list[str] = []
    for match in _CELL.finditer(xml):
        cell = match.group(0)
        if _FORMULA.search(cell) is None:
            continue
        reference = _REFERENCE.search(cell)
        if reference is None:
            raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", "formula without ref")
        coordinates.append(reference.group(2).decode("ascii"))
    if len(coordinates) != len(set(coordinates)):
        raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", "duplicate formula ref")
    return tuple(coordinates)


def numeric_formula_values(xml: bytes, coordinates: tuple[str, ...]) -> dict[str, str]:
    """Extract validated numeric values for requested coordinates from LibreOffice XML."""

    requested = set(coordinates)
    values: dict[str, str] = {}
    for match in _CELL.finditer(xml):
        cell = match.group(0)
        reference = _REFERENCE.search(cell)
        if reference is None:
            continue
        coordinate = reference.group(2).decode("ascii")
        if coordinate not in requested:
            continue
        values[coordinate] = _finite_numeric_lexeme(cell, coordinate)
    if set(values) != requested:
        missing = next(iter(requested.difference(values)), "unknown")
        raise ExcelWriterIntegrityError("FORMULA_RESULT_NOT_NUMERIC", missing)
    return values


def materialize_formula_cells(xml: bytes, values: Mapping[str, str]) -> bytes:
    """Replace authoritative worksheet formulas using LibreOffice numeric results."""

    pieces: list[bytes] = []
    cursor = 0
    for match in _CELL.finditer(xml):
        cell = match.group(0)
        if _FORMULA.search(cell) is None:
            continue
        reference = _REFERENCE.search(cell)
        if reference is None:
            raise ExcelWriterIntegrityError("FORMULA_MATERIALIZATION_FAILED", "formula without ref")
        coordinate = reference.group(2).decode("ascii")
        decimal_text = values.get(coordinate)
        if decimal_text is None:
            raise ExcelWriterIntegrityError("FORMULA_RESULT_NOT_NUMERIC", coordinate)
        updated = _FORMULA.sub(b"", cell)
        updated = _TYPE.sub(b"", updated)
        updated = replace_cell_value(updated, coordinate, decimal_text)
        pieces.extend((xml[cursor : match.start()], updated))
        cursor = match.end()
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
                for coordinate, decimal_text in changes_by_part.get(info.filename, ()):
                    payload = replace_cell_value(payload, coordinate, decimal_text)
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
                for coordinate, decimal_text in changes_by_part.get(name, ()):
                    expected = replace_cell_value(expected, coordinate, decimal_text)
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


def _finite_numeric_lexeme(cell: bytes, coordinate: str) -> str:
    cell_type = _TYPE.search(cell)
    if cell_type is not None and cell_type.group(2) not in {b"n"}:
        raise ExcelWriterIntegrityError("FORMULA_RESULT_NOT_NUMERIC", coordinate)
    value = _VALUE.search(cell)
    if value is None or value.group(1) is None:
        raise ExcelWriterIntegrityError("FORMULA_RESULT_NOT_NUMERIC", coordinate)
    decimal_text = value.group(1).decode("ascii")
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
