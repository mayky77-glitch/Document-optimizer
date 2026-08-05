"""Package-preserving red row annotations for reconciliation review copies."""

from __future__ import annotations

import hashlib
import os
import re
import stat
import tempfile
import zipfile
from collections.abc import Collection, Mapping
from pathlib import Path
from xml.etree import ElementTree

from report_processor.materialization import is_unsafe_archive_path

from .exceptions import (
    ExcelWriterAtomicError,
    ExcelWriterInputError,
    ExcelWriterIntegrityError,
    ExcelWriterSafetyError,
)
from .ooxml import publish_no_clobber, reject_unsupported_package, worksheet_part_map

_CELL = re.compile(rb"<c\b[^>]*?(?:/>|>.*?</c>)", re.DOTALL)
_ROW = re.compile(rb"<row\b[^>]*?(?:/>|>.*?</row>)", re.DOTALL)
_REFERENCE = re.compile(rb"\br\s*=\s*([\"'])([^\"']+)\1")
_STYLE = re.compile(rb"\bs\s*=\s*([\"'])([^\"']+)\1")
_MAX_EXCEL_ROW = 1_048_576
_RED_FILL = "FFFF0000"


def annotate_failed_rows(
    source_path: Path,
    output_path: Path,
    failed_rows: Mapping[str, Collection[int]],
) -> Path:
    """Publish a private OOXML copy with existing failed-row cells filled red.

    The source package is never changed.  Only ``xl/styles.xml`` and worksheet
    parts that contain selected cells may differ in the published archive.
    """

    source = Path(source_path)
    output = Path(output_path)
    _validate_paths(source, output)
    rows_by_sheet = _validated_failed_rows(failed_rows)
    if output.exists():
        raise ExcelWriterSafetyError("OUTPUT_EXISTS", str(output))

    source_digest = _sha256(source)
    reject_unsupported_package(source)
    _reject_unsafe_package_entries(source)
    parts = worksheet_part_map(source)
    unknown_sheets = set(rows_by_sheet).difference(parts)
    if unknown_sheets:
        raise ExcelWriterInputError("UNKNOWN_WORKSHEET", min(unknown_sheets))

    try:
        with zipfile.ZipFile(source) as archive:
            sheet_payloads = {
                parts[sheet_name]: archive.read(parts[sheet_name]) for sheet_name in rows_by_sheet
            }
            selected_styles = set().union(
                *(
                    _selected_style_ids(sheet_payloads[parts[sheet_name]], rows)
                    for sheet_name, rows in rows_by_sheet.items()
                )
            )
            updated_sheets: dict[str, bytes] = {}
            updated_styles: bytes | None = None
            style_variants: dict[int, int] = {}
            if selected_styles:
                try:
                    styles = archive.read("xl/styles.xml")
                except KeyError as error:
                    raise ExcelWriterIntegrityError("STYLES_MISSING", "xl/styles.xml") from error
                updated_styles, style_variants = _red_style_variants(styles, selected_styles)
                for sheet_name, rows in rows_by_sheet.items():
                    xml = sheet_payloads[parts[sheet_name]]
                    updated = _apply_style_variants(xml, rows, style_variants)
                    if updated != xml:
                        updated_sheets[parts[sheet_name]] = updated
            changes = dict(updated_sheets)
            if updated_styles is not None:
                changes["xl/styles.xml"] = updated_styles
            temp_path = _temporary_path(output)
            try:
                _write_package_copy(source, temp_path, changes)
                _verify_package_copy(source, temp_path, changes)
                _assert_source_digest(source, source_digest)
                publish_no_clobber(temp_path, output)
            finally:
                temp_path.unlink(missing_ok=True)
    except (ExcelWriterAtomicError, ExcelWriterInputError, ExcelWriterIntegrityError):
        raise
    except ExcelWriterSafetyError:
        raise
    except (OSError, ValueError, zipfile.BadZipFile, ElementTree.ParseError) as error:
        raise ExcelWriterIntegrityError("ROW_ANNOTATION_FAILED", str(error)) from error
    return output


def _validate_paths(source: Path, output: Path) -> None:
    if source.suffix.casefold() not in {".xlsx", ".xlsm", ".xltx", ".xltm"}:
        raise ExcelWriterSafetyError("INVALID_SOURCE", str(source))
    if not source.is_file() or not stat.S_ISREG(source.stat().st_mode):
        raise ExcelWriterSafetyError("INVALID_SOURCE", str(source))
    if output.suffix.casefold() != source.suffix.casefold():
        raise ExcelWriterSafetyError("INVALID_OUTPUT_EXTENSION", str(output))
    if not output.parent.is_dir():
        raise ExcelWriterSafetyError("INVALID_OUTPUT", str(output.parent))
    if source.resolve() == output.resolve(strict=False):
        raise ExcelWriterSafetyError("SOURCE_OUTPUT_IDENTITY", str(source))


def _validated_failed_rows(value: object) -> dict[str, frozenset[int]]:
    if not isinstance(value, Mapping) or not value:
        raise ExcelWriterInputError("INVALID_FAILED_ROWS", "a non-empty mapping is required")
    result: dict[str, frozenset[int]] = {}
    for sheet_name, rows in value.items():
        if (
            not isinstance(sheet_name, str)
            or not sheet_name
            or any(ord(character) < 32 for character in sheet_name)
            or not isinstance(rows, Collection)
            or isinstance(rows, (str, bytes, bytearray))
        ):
            raise ExcelWriterInputError("INVALID_FAILED_ROWS", "invalid sheet rows")
        normalized = frozenset(rows)
        if not normalized or any(
            not isinstance(row, int) or isinstance(row, bool) or not 0 < row <= _MAX_EXCEL_ROW
            for row in normalized
        ):
            raise ExcelWriterInputError("INVALID_FAILED_ROWS", sheet_name)
        result[sheet_name] = normalized
    return result


def _reject_unsafe_package_entries(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if is_unsafe_archive_path(info.filename) or stat.S_ISLNK(info.external_attr >> 16):
                    raise ExcelWriterSafetyError("INVALID_XLSX_PACKAGE", info.filename)
    except ExcelWriterSafetyError:
        raise
    except (OSError, zipfile.BadZipFile) as error:
        raise ExcelWriterSafetyError("INVALID_XLSX_PACKAGE", str(error)) from error


def _selected_style_ids(xml: bytes, rows: Collection[int]) -> set[int]:
    selected: set[int] = set()
    found_rows: set[int] = set()
    for row in _ROW.finditer(xml):
        row_xml = row.group(0)
        reference = _REFERENCE.search(row_xml)
        if reference is None:
            continue
        try:
            row_number = int(reference.group(2))
        except ValueError as error:
            raise ExcelWriterIntegrityError("INVALID_WORKSHEET_XML", "row reference") from error
        if row_number not in rows:
            continue
        row_has_cells = False
        for match in _CELL.finditer(row_xml):
            row_has_cells = True
            selected.add(_style_id(match.group(0)))
        if row_has_cells:
            found_rows.add(row_number)
    missing_rows = set(rows).difference(found_rows)
    if missing_rows:
        raise ExcelWriterIntegrityError("FAILED_ROW_NOT_FOUND", str(min(missing_rows)))
    return selected


def _style_id(cell: bytes) -> int:
    opening = cell[: cell.find(b">") + 1]
    style = _STYLE.search(opening)
    if style is None:
        return 0
    try:
        value = int(style.group(2))
    except ValueError as error:
        raise ExcelWriterIntegrityError("INVALID_WORKSHEET_XML", "style reference") from error
    if value < 0:
        raise ExcelWriterIntegrityError("INVALID_WORKSHEET_XML", "style reference")
    return value


def _red_style_variants(styles: bytes, style_ids: Collection[int]) -> tuple[bytes, dict[int, int]]:
    """Add style variants without reserializing unrelated namespace metadata."""

    root = ElementTree.fromstring(styles)
    namespace = root.tag.partition("}")[0].removeprefix("{")
    qualified = lambda name: f"{{{namespace}}}{name}" if namespace else name  # noqa: E731
    fills = root.find(qualified("fills"))
    cell_xfs = root.find(qualified("cellXfs"))
    if fills is None or cell_xfs is None:
        raise ExcelWriterIntegrityError("STYLES_MISSING", "fills or cellXfs")
    base_xfs = list(cell_xfs)
    if any(style_id >= len(base_xfs) for style_id in style_ids):
        raise ExcelWriterIntegrityError("INVALID_WORKSHEET_XML", "style reference")
    fills_section = _xml_section(styles, b"fills")
    cell_xfs_section = _xml_section(styles, b"cellXfs")
    raw_xfs = _xml_children(cell_xfs_section.group("body"), cell_xfs_section.group("qname"), b"xf")
    if len(raw_xfs) != len(base_xfs):
        raise ExcelWriterIntegrityError("STYLES_MISSING", "cellXfs structure")
    red_fill_id = _red_fill_id(fills, qualified)
    if red_fill_id is None:
        red_fill_id = len(fills)
        prefix = _xml_prefix(fills_section.group("qname"))
        red_fill = (
            b"<"
            + prefix
            + b"fill><"
            + prefix
            + b'patternFill patternType="solid"><'
            + prefix
            + b'fgColor rgb="'
            + _RED_FILL.encode("ascii")
            + b'"/><'
            + prefix
            + b'bgColor indexed="64"/></'
            + prefix
            + b"patternFill></"
            + prefix
            + b"fill>"
        )
        styles = _append_xml_children(styles, fills_section, red_fill, len(fills) + 1)
        cell_xfs_section = _xml_section(styles, b"cellXfs")
    variants: dict[int, int] = {}
    raw_variants: list[bytes] = []
    for style_id in sorted(style_ids):
        variants[style_id] = len(base_xfs) + len(raw_variants)
        raw_variants.append(_style_variant(raw_xfs[style_id], red_fill_id))
    updated = _append_xml_children(
        styles,
        cell_xfs_section,
        b"".join(raw_variants),
        len(base_xfs) + len(raw_variants),
    )
    return updated, variants


def _red_fill_id(fills: ElementTree.Element, qualified) -> int | None:
    for fill_id, fill in enumerate(fills):
        pattern = fill.find(qualified("patternFill"))
        foreground = None if pattern is None else pattern.find(qualified("fgColor"))
        if (
            pattern is not None
            and pattern.attrib.get("patternType") == "solid"
            and foreground is not None
            and foreground.attrib.get("rgb", "").upper() == _RED_FILL
        ):
            return fill_id
    return None


def _xml_section(xml: bytes, local_name: bytes):
    name = rb"(?P<qname>(?:[A-Za-z_][\w.-]*:)?" + re.escape(local_name) + rb")"
    pattern = re.compile(rb"<" + name + rb"\b[^>]*>(?P<body>.*?)</(?P=qname)\s*>", re.DOTALL)
    match = pattern.search(xml)
    if match is None:
        raise ExcelWriterIntegrityError("STYLES_MISSING", local_name.decode("ascii"))
    return match


def _xml_prefix(qname: bytes) -> bytes:
    return qname.rpartition(b":")[0] + b":" if b":" in qname else b""


def _xml_children(body: bytes, parent_qname: bytes, local_name: bytes) -> list[bytes]:
    qname = _xml_prefix(parent_qname) + local_name
    pattern = re.compile(
        rb"<" + re.escape(qname) + rb"\b[^>]*(?:/>|>.*?</" + re.escape(qname) + rb"\s*>)",
        re.DOTALL,
    )
    return [match.group(0) for match in pattern.finditer(body)]


def _append_xml_children(xml: bytes, section, children: bytes, count: int) -> bytes:
    section_xml = section.group(0)
    body_start = section.start("body") - section.start()
    body_end = section.end("body") - section.start()
    opening = _set_xml_attribute(section_xml[:body_start], b"count", str(count).encode("ascii"))
    updated = opening + section_xml[body_start:body_end] + children + section_xml[body_end:]
    return xml[: section.start()] + updated + xml[section.end() :]


def _style_variant(style: bytes, fill_id: int) -> bytes:
    opening_end = style.find(b">") + 1
    if opening_end == 0:
        raise ExcelWriterIntegrityError("STYLES_MISSING", "xf opening tag")
    opening = _set_xml_attribute(style[:opening_end], b"fillId", str(fill_id).encode("ascii"))
    opening = _set_xml_attribute(opening, b"applyFill", b"1")
    return opening + style[opening_end:]


def _set_xml_attribute(opening: bytes, name: bytes, value: bytes) -> bytes:
    attribute = re.compile(rb"\b" + re.escape(name) + rb"\s*=\s*([\"'])[^\"']*\1")
    match = attribute.search(opening)
    replacement = name + b'="' + value + b'"'
    if match is not None:
        return opening[: match.start()] + replacement + opening[match.end() :]
    insertion = opening.rfind(b"/>")
    if insertion < 0:
        insertion = opening.rfind(b">")
    if insertion < 0:
        raise ExcelWriterIntegrityError("STYLES_MISSING", name.decode("ascii"))
    return opening[:insertion] + b" " + replacement + opening[insertion:]


def _apply_style_variants(xml: bytes, rows: Collection[int], variants: Mapping[int, int]) -> bytes:
    pieces: list[bytes] = []
    cursor = 0
    for row in _ROW.finditer(xml):
        row_xml = row.group(0)
        reference = _REFERENCE.search(row_xml)
        if reference is None or int(reference.group(2)) not in rows:
            continue
        updated_row = _update_row_cells(row_xml, variants)
        pieces.extend((xml[cursor : row.start()], updated_row))
        cursor = row.end()
    if cursor == 0:
        return xml
    pieces.append(xml[cursor:])
    return b"".join(pieces)


def _update_row_cells(row_xml: bytes, variants: Mapping[int, int]) -> bytes:
    pieces: list[bytes] = []
    cursor = 0
    for match in _CELL.finditer(row_xml):
        cell = match.group(0)
        updated = _replace_style(cell, variants[_style_id(cell)])
        pieces.extend((row_xml[cursor : match.start()], updated))
        cursor = match.end()
    pieces.append(row_xml[cursor:])
    return b"".join(pieces)


def _replace_style(cell: bytes, style_id: int) -> bytes:
    opening_end = cell.find(b">") + 1
    opening = cell[:opening_end]
    style = _STYLE.search(opening)
    replacement = str(style_id).encode("ascii")
    if style is not None:
        return (
            opening[: style.start(2)] + replacement + opening[style.end(2) :] + cell[opening_end:]
        )
    insertion = b' s="' + replacement + b'"'
    if opening.endswith(b"/>"):
        opening = opening[:-2] + insertion + b"/>"
    else:
        opening = opening[:-1] + insertion + b">"
    return opening + cell[opening_end:]


def _temporary_path(output: Path) -> Path:
    descriptor, name = tempfile.mkstemp(
        prefix=".row-annotation-", suffix=output.suffix + ".tmp", dir=output.parent
    )
    os.close(descriptor)
    return Path(name)


def _write_package_copy(source_path: Path, temp_path: Path, changes: Mapping[str, bytes]) -> None:
    try:
        with (
            zipfile.ZipFile(source_path) as source,
            zipfile.ZipFile(temp_path, "w", allowZip64=True) as output,
        ):
            output.comment = source.comment
            for info in source.infolist():
                output.writestr(info, changes.get(info.filename, source.read(info.filename)))
        _fsync_file(temp_path)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        raise ExcelWriterAtomicError("ATOMIC_PUBLISH_FAILED", str(error)) from error


def _verify_package_copy(source_path: Path, temp_path: Path, changes: Mapping[str, bytes]) -> None:
    try:
        with zipfile.ZipFile(source_path) as source, zipfile.ZipFile(temp_path) as output:
            if tuple(source.namelist()) != tuple(output.namelist()) or output.testzip() is not None:
                raise ExcelWriterIntegrityError(
                    "PRESERVATION_CHECK_FAILED", "package structure changed"
                )
            for name in source.namelist():
                expected = changes.get(name, source.read(name))
                if output.read(name) != expected:
                    raise ExcelWriterIntegrityError("PRESERVATION_CHECK_FAILED", name)
    except ExcelWriterIntegrityError:
        raise
    except (OSError, KeyError, zipfile.BadZipFile) as error:
        raise ExcelWriterIntegrityError("PRESERVATION_CHECK_FAILED", str(error)) from error


def _assert_source_digest(path: Path, expected: str) -> None:
    if _sha256(path) != expected:
        raise ExcelWriterIntegrityError("SOURCE_CHANGED_DURING_WRITE", str(path))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_file(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
