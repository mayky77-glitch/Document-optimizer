"""Plan, verify, and atomically publish targeted XLSX value updates."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
import zipfile
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path

from openpyxl.utils.cell import range_boundaries

from report_processor.calculation import CalculationResult, CalculationStatus
from report_processor.quality_control import WriteDecision
from report_processor.schema import LogicalColumn
from report_processor.target_report import TargetReportSchema

from .exceptions import (
    ExcelWriterAtomicError,
    ExcelWriterInputError,
    ExcelWriterIntegrityError,
    ExcelWriterSafetyError,
)
from .formula_materialization import recalculate_and_materialize
from .models import EXCEL_WRITER_CONTRACT_VERSION, WriteResult, WriteStatus, WrittenCell
from .ooxml import (
    WorksheetIndex,
    admitted_zipfile,
    inspect_index_cell,
    package_has_formulas,
    read_archive_part,
    reject_unsupported_package,
    validate_xlsx_source,
    verify_formula_free_package,
    worksheet_index,
    worksheet_part_map,
)
from .ooxml import (
    publish_no_clobber as _publish_no_clobber,
)
from .ooxml import (
    verify_temp_package as _verify_temp_package,
)
from .ooxml import (
    write_temp_package as _write_temp_package,
)

_WRITABLE_DECISIONS = frozenset(
    (WriteDecision.ALLOW_WRITE, WriteDecision.ALLOW_WRITE_WITH_WARNINGS)
)
_CALCULATED_STATUSES = frozenset(
    (CalculationStatus.CALCULATED, CalculationStatus.CALCULATED_WITH_WARNINGS)
)
_ALLOWED_COLUMNS = (
    (LogicalColumn.CURRENT_PERIOD_QUANTITY, "quantity"),
    (LogicalColumn.CURRENT_PERIOD_COST, "cost"),
)


@dataclass(frozen=True, slots=True)
class _SourceIdentity:
    device: int
    inode: int
    size: int
    mtime_ns: int
    sha256: str


@dataclass(frozen=True, slots=True)
class _PublishedOutputIdentity:
    device: int
    inode: int


@dataclass(frozen=True, slots=True)
class _SourceSnapshot:
    path: Path
    descriptor: int
    identity: _SourceIdentity


def write_target_report(
    source_path: str | Path,
    output_path: str | Path,
    decision: WriteDecision,
    calculation_results: Iterable[CalculationResult],
    target_schema: TargetReportSchema,
) -> WriteResult:
    """Write only approved Decimal values, preserving every other OOXML part."""

    source = Path(source_path)
    output = Path(output_path)
    _validate_public_inputs(source, output, decision, target_schema)
    snapshot = _snapshot_source(source, output.parent)
    snapshot_path, source_identity = snapshot.path, snapshot.identity
    temp_path: Path | None = None
    published = False
    published_identity: _PublishedOutputIdentity | None = None
    try:
        _validate_schema_identity(source, source_identity, target_schema)
        if decision not in _WRITABLE_DECISIONS:
            result = _result(
                WriteStatus.SKIPPED_DECISION,
                decision,
                target_schema,
                source_identity.sha256,
                None,
                None,
                (),
                (),
                (),
            )
            return result
        if output.exists():
            raise ExcelWriterSafetyError("OUTPUT_EXISTS", str(output))
        calculations = _validated_calculations(calculation_results)
        reject_unsupported_package(snapshot.descriptor)
        parts = worksheet_part_map(snapshot.descriptor)
        written_cells = _build_write_plan(snapshot.descriptor, calculations, target_schema, parts)
        if not written_cells:
            raise ExcelWriterInputError("EMPTY_WRITE_SET", "no non-None calculated values")
        changes_by_part = _changes_by_part(written_cells, parts)
        temp_path = _temp_path(output)
        worksheet_parts = frozenset(parts.values())
        _write_temp_package(
            snapshot.descriptor,
            temp_path,
            changes_by_part,
            remove_calc_chain=True,
            worksheet_parts=worksheet_parts,
        )
        _verify_temp_package(
            snapshot.descriptor,
            temp_path,
            changes_by_part,
            remove_calc_chain=True,
            worksheet_parts=worksheet_parts,
        )
        if package_has_formulas(temp_path, parts):
            recalculate_and_materialize(temp_path)
        verify_formula_free_package(temp_path, parts)
        _assert_source_unchanged(source, source_identity)
        published_identity = _published_output_identity(temp_path)
        _publish_no_clobber(temp_path, output)
        published = True
        output_sha256 = _sha256(output)
        _reopen_published_output(output)
        return _result(
            WriteStatus.WRITTEN,
            decision,
            target_schema,
            source_identity.sha256,
            output,
            output_sha256,
            written_cells,
            tuple(sorted(item.calculation_id for item in calculations)),
            ("QUALITY_GATE_WARNINGS_PRESENT",)
            if decision is WriteDecision.ALLOW_WRITE_WITH_WARNINGS
            else (),
        )
    except (ExcelWriterAtomicError, ExcelWriterIntegrityError, ExcelWriterSafetyError):
        if published:
            _remove_published_output_if_owned(output, published_identity)
        raise
    except OSError as error:
        if published:
            _remove_published_output_if_owned(output, published_identity)
        raise ExcelWriterAtomicError("ATOMIC_PUBLISH_FAILED", str(error)) from error
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        os.close(snapshot.descriptor)
        snapshot_path.unlink(missing_ok=True)


def _validate_public_inputs(
    source: Path, output: Path, decision: object, target_schema: object
) -> None:
    if not isinstance(decision, WriteDecision):
        raise ExcelWriterInputError("INVALID_CALCULATION_RESULT", "decision must be WriteDecision")
    if not isinstance(target_schema, TargetReportSchema):
        raise ExcelWriterInputError(
            "INVALID_SCHEMA_STATUS", "target_schema must be TargetReportSchema"
        )
    if source.suffix.casefold() != ".xlsx" or not source.exists() or not source.is_file():
        raise ExcelWriterSafetyError("INVALID_SOURCE", str(source))
    if not stat.S_ISREG(source.stat().st_mode):
        raise ExcelWriterSafetyError("INVALID_SOURCE", "source is not a regular file")
    validate_xlsx_source(source, ExcelWriterSafetyError, "INVALID_XLSX_PACKAGE")
    if output.suffix.casefold() != ".xlsx":
        raise ExcelWriterSafetyError("INVALID_OUTPUT_EXTENSION", str(output))
    if not output.parent.is_dir():
        raise ExcelWriterSafetyError(
            "INVALID_SOURCE", f"output directory is missing: {output.parent}"
        )
    if source.resolve() == output.resolve(strict=False):
        raise ExcelWriterSafetyError("SOURCE_OUTPUT_IDENTITY", str(source))


def _validate_schema_identity(
    source: Path, identity: _SourceIdentity, schema: TargetReportSchema
) -> None:
    fingerprint = schema.source_fingerprint
    if schema.status != "OK" or schema.diagnostics:
        raise ExcelWriterInputError("INVALID_SCHEMA_STATUS", schema.status)
    if (
        fingerprint.algorithm != "sha256"
        or fingerprint.digest != identity.sha256
        or fingerprint.size_bytes != identity.size
        or schema.source_sha256 != identity.sha256
        or not schema.source_file_id
        or fingerprint.source_file_id != schema.source_file_id
        or source.name != schema.filename
    ):
        raise ExcelWriterIntegrityError("SOURCE_FINGERPRINT_MISMATCH", str(source))


def _validated_calculations(values: Iterable[CalculationResult]) -> tuple[CalculationResult, ...]:
    try:
        calculations = tuple(values)
    except TypeError as error:
        raise ExcelWriterInputError("INVALID_CALCULATION_RESULT", str(error)) from error
    if not calculations:
        raise ExcelWriterInputError("EMPTY_WRITE_SET", "calculation_results is empty")
    identifiers: set[str] = set()
    row_identifiers: set[str] = set()
    for calculation in calculations:
        if not isinstance(calculation, CalculationResult):
            raise ExcelWriterInputError("INVALID_CALCULATION_RESULT", repr(calculation))
        if calculation.calculation_id in identifiers:
            raise ExcelWriterInputError("DUPLICATE_CALCULATION_ID", calculation.calculation_id)
        if calculation.target_row_id in row_identifiers:
            raise ExcelWriterInputError("DUPLICATE_TARGET_ROW_ID", calculation.target_row_id)
        if calculation.status not in _CALCULATED_STATUSES:
            raise ExcelWriterInputError("UNSUPPORTED_CALCULATION_STATUS", calculation.status.value)
        identifiers.add(calculation.calculation_id)
        row_identifiers.add(calculation.target_row_id)
    return tuple(sorted(calculations, key=lambda item: item.calculation_id))


def _build_write_plan(
    source: Path | int,
    calculations: tuple[CalculationResult, ...],
    schema: TargetReportSchema,
    parts: dict[str, str],
) -> tuple[WrittenCell, ...]:
    worksheets = {item.sheet_name: item for item in schema.worksheets}
    bindings: defaultdict[LogicalColumn, list] = defaultdict(list)
    for binding in schema.column_bindings:
        bindings[binding.logical_column].append(binding)
    source_xml: dict[str, bytes] = {}
    source_indexes: dict[str, WorksheetIndex] = {}
    seen_coordinates: set[tuple[str, str]] = set()
    plan: list[WrittenCell] = []
    try:
        with admitted_zipfile(source, ExcelWriterIntegrityError, "TARGET_CELL_MISSING") as archive:
            for calculation in calculations:
                row = calculation.target_row
                if not row.writable:
                    raise ExcelWriterInputError("TARGET_NOT_WRITABLE", calculation.target_row_id)
                worksheet = worksheets.get(row.sheet_name)
                part = parts.get(row.sheet_name)
                if worksheet is None or part is None:
                    raise ExcelWriterIntegrityError("TARGET_SHEET_MISSING", row.sheet_name)
                if part not in source_xml:
                    source_xml[part] = read_archive_part(
                        archive,
                        part,
                        ExcelWriterIntegrityError,
                        "TARGET_CELL_MISSING",
                        worksheet=True,
                    )
                    source_indexes[part] = worksheet_index(source_xml[part])
                for logical_column, attribute in _ALLOWED_COLUMNS:
                    value = getattr(calculation, attribute)
                    if value is None:
                        continue
                    decimal_text = _decimal_text(value)
                    target_cell = row.cell_for(logical_column)
                    if not bindings[logical_column]:
                        continue
                    matching_bindings = [
                        item
                        for item in bindings[logical_column]
                        if target_cell is not None
                        and item.column_letter + str(row.row_number) == target_cell.coordinate
                    ]
                    if len(matching_bindings) != 1:
                        raise ExcelWriterIntegrityError(
                            "TARGET_COLUMN_BINDING_MISSING", f"{row.sheet_name}!{logical_column}"
                        )
                    if target_cell is None or target_cell.coordinate != (
                        matching_bindings[0].column_letter + str(row.row_number)
                    ):
                        raise ExcelWriterIntegrityError(
                            "TARGET_IDENTITY_MISMATCH", calculation.target_row_id
                        )
                    coordinate_key = (row.sheet_name, target_cell.coordinate)
                    if coordinate_key in seen_coordinates:
                        raise ExcelWriterInputError(
                            "DUPLICATE_WRITE_COORDINATE",
                            f"{row.sheet_name}!{target_cell.coordinate}",
                        )
                    _validate_target_cell(
                        source_indexes[part],
                        target_cell.coordinate,
                        target_cell.raw_lexeme,
                        target_cell.formula is not None,
                        worksheet.merged_ranges,
                    )
                    seen_coordinates.add(coordinate_key)
                    plan.append(
                        WrittenCell(
                            calculation.calculation_id,
                            calculation.target_row_id,
                            row.sheet_name,
                            row.row_number,
                            target_cell.coordinate,
                            logical_column,
                            decimal_text,
                        )
                    )
    except (OSError, zipfile.BadZipFile) as error:
        raise ExcelWriterSafetyError("INVALID_XLSX_PACKAGE", str(error)) from error
    return tuple(
        sorted(plan, key=lambda item: (item.sheet_name, item.coordinate, item.calculation_id))
    )


def _validate_target_cell(
    index: WorksheetIndex,
    coordinate: str,
    expected_lexeme: str | None,
    has_snapshot_formula: bool,
    merged_ranges: tuple[str, ...],
) -> None:
    if _is_merged(coordinate, merged_ranges):
        raise ExcelWriterIntegrityError("TARGET_CELL_IS_MERGED", coordinate)
    _, actual_lexeme, is_formula, has_style, cell_type = inspect_index_cell(index, coordinate)
    if not has_style:
        raise ExcelWriterIntegrityError("TARGET_CELL_MISSING", f"missing style: {coordinate}")
    if cell_type not in {None, "n"}:
        raise ExcelWriterIntegrityError("TARGET_CELL_LEXEME_MISMATCH", coordinate)
    if has_snapshot_formula or is_formula:
        raise ExcelWriterIntegrityError("TARGET_CELL_IS_FORMULA", coordinate)
    if actual_lexeme != expected_lexeme:
        raise ExcelWriterIntegrityError("TARGET_CELL_LEXEME_MISMATCH", coordinate)


def _is_merged(coordinate: str, merged_ranges: tuple[str, ...]) -> bool:
    from openpyxl.utils.cell import column_index_from_string, coordinate_from_string

    column_letters, row = coordinate_from_string(coordinate)
    column = column_index_from_string(column_letters)
    for merged_range in merged_ranges:
        minimum_column, minimum_row, maximum_column, maximum_row = range_boundaries(merged_range)
        if minimum_column <= column <= maximum_column and minimum_row <= row <= maximum_row:
            return True
    return False


def _decimal_text(value: object) -> str:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ExcelWriterInputError("INVALID_DECIMAL", repr(value))
    return format(value, "f")


def _changes_by_part(
    written_cells: tuple[WrittenCell, ...], parts: dict[str, str]
) -> dict[str, tuple[tuple[str, str], ...]]:
    changes: defaultdict[str, list[tuple[str, str]]] = defaultdict(list)
    for cell in written_cells:
        changes[parts[cell.sheet_name]].append((cell.coordinate, cell.decimal_text))
    return {part: tuple(items) for part, items in changes.items()}


def _temp_path(output: Path) -> Path:
    descriptor, name = tempfile.mkstemp(prefix=".excel-writer-", suffix=".xlsx", dir=output.parent)
    os.close(descriptor)
    return Path(name)


def _source_identity(path: Path) -> _SourceIdentity:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size > 256 * 1024 * 1024:
            raise ExcelWriterSafetyError("INVALID_SOURCE", "source is not a bounded regular file")
        digest = hashlib.sha256()
        size = 0
        while chunk := os.read(descriptor, 1_048_576):
            size += len(chunk)
            if size > 256 * 1024 * 1024:
                raise ExcelWriterSafetyError("INVALID_SOURCE", "source exceeds limit")
            digest.update(chunk)
        after = os.fstat(descriptor)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ) or size != before.st_size:
            raise ExcelWriterIntegrityError("SOURCE_CHANGED_DURING_WRITE", str(path))
        return _SourceIdentity(
            before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, digest.hexdigest()
        )
    finally:
        os.close(descriptor)


def _snapshot_source(source: Path, directory: Path) -> _SourceSnapshot:
    """Capture one verified source fd before any hash or ZIP operation."""

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(source, flags)
    snapshot_descriptor = -1
    snapshot_name = ""
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode) or details.st_size > 256 * 1024 * 1024:
            raise ExcelWriterSafetyError("INVALID_XLSX_PACKAGE", "source is not a regular file")
        snapshot_descriptor, snapshot_name = tempfile.mkstemp(
            prefix=".excel-writer-source-", suffix=".xlsx", dir=directory
        )
        os.fchmod(snapshot_descriptor, 0o600)
        digest = hashlib.sha256()
        copied = 0
        while chunk := os.read(descriptor, 1_048_576):
            copied += len(chunk)
            if copied > 256 * 1024 * 1024:
                raise ExcelWriterSafetyError("INVALID_XLSX_PACKAGE", "source exceeds limit")
            digest.update(chunk)
            _write_all(snapshot_descriptor, chunk)
        final_details = os.fstat(descriptor)
        if (details.st_dev, details.st_ino, details.st_size, details.st_mtime_ns) != (
            final_details.st_dev,
            final_details.st_ino,
            final_details.st_size,
            final_details.st_mtime_ns,
        ) or copied != details.st_size:
            raise ExcelWriterIntegrityError("SOURCE_CHANGED_DURING_WRITE", str(source))
        os.fsync(snapshot_descriptor)
        return _SourceSnapshot(
            Path(snapshot_name),
            snapshot_descriptor,
            _SourceIdentity(
                final_details.st_dev,
                final_details.st_ino,
                final_details.st_size,
                final_details.st_mtime_ns,
                digest.hexdigest(),
            ),
        )
    except BaseException:
        if snapshot_name:
            Path(snapshot_name).unlink(missing_ok=True)
        if snapshot_descriptor >= 0:
            os.close(snapshot_descriptor)
            snapshot_descriptor = -1
        raise
    finally:
        os.close(descriptor)
        if snapshot_descriptor >= 0 and not snapshot_name:
            os.close(snapshot_descriptor)


def _assert_source_unchanged(path: Path, expected: _SourceIdentity) -> None:
    actual = _source_identity(path)
    if actual != expected:
        raise ExcelWriterIntegrityError("SOURCE_CHANGED_DURING_WRITE", str(path))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_all(descriptor: int, payload: bytes) -> None:
    """Do not silently accept a short write while capturing the source snapshot."""

    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            raise OSError("short snapshot write")
        offset += written


def _published_output_identity(path: Path) -> _PublishedOutputIdentity:
    details = path.stat()
    return _PublishedOutputIdentity(details.st_dev, details.st_ino)


def _remove_published_output_if_owned(
    path: Path, identity: _PublishedOutputIdentity | None
) -> None:
    """Remove a failed publication only when its pathname still has our inode."""

    if identity is None:
        return
    try:
        if _published_output_identity(path) == identity:
            path.unlink()
    except FileNotFoundError:
        return


def _reopen_published_output(output: Path) -> None:
    try:
        from openpyxl import load_workbook

        workbook = load_workbook(output, read_only=True, data_only=False, keep_links=True)
        workbook.close()
    except Exception as error:
        raise ExcelWriterIntegrityError("REOPEN_FAILED", str(error)) from error


def _result(
    status: WriteStatus,
    decision: WriteDecision,
    schema: TargetReportSchema,
    source_sha256: str,
    output: Path | None,
    output_sha256: str | None,
    written_cells: tuple[WrittenCell, ...],
    calculation_ids: tuple[str, ...],
    warnings: tuple[str, ...],
) -> WriteResult:
    payload = {
        "contract": EXCEL_WRITER_CONTRACT_VERSION,
        "decision": decision.value,
        "source_file_id": schema.source_file_id,
        "source_sha256": source_sha256,
        "output_sha256": output_sha256,
        "calculation_ids": list(calculation_ids),
        "written_cells": [
            {
                **asdict(item),
                "logical_column": item.logical_column.value,
            }
            for item in written_cells
        ],
    }
    write_id = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return WriteResult(
        write_id,
        status,
        decision,
        schema.source_file_id,
        source_sha256,
        str(output) if output is not None else None,
        output_sha256,
        written_cells,
        calculation_ids,
        warnings,
    )
