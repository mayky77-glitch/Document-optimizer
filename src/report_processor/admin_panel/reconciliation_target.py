"""Adapter for the documented additional-report reconciliation layout."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
from collections.abc import Iterable
from dataclasses import replace
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from report_processor.excel import WorkbookOpenRequest, open_dual_workbook
from report_processor.identifiers import extract_document_index
from report_processor.processing.adapters import _materialized
from report_processor.schema import LogicalColumn, SheetType, analyze_workbook_schema
from report_processor.target_report import (
    TargetColumnBinding,
    TargetReportReadRequest,
    TargetReportRow,
)
from report_processor.target_report.ooxml import (
    formula_caches_trusted,
    read_sheet_comments,
    read_sheet_lexemes,
)
from report_processor.target_report.reader import _cell_snapshot

_STAGE_RE = re.compile(r"этап\s*([0-9]+(?:\.[0-9]+)*)", re.IGNORECASE)


class ReconciliationTargetScopeError(ValueError):
    """The target cannot supply one safe reconciliation stage."""


def publish_unchanged_target(source, output, expected_sha256: str) -> str:
    """Atomically publish one verified byte-identical target copy without clobbering."""
    source_path, output_path = Path(source), Path(output)
    if output_path.exists() or output_path.is_symlink():
        raise ValueError("RECONCILIATION_OUTPUT_EXISTS")
    source_sha256 = _sha256(source_path)
    if source_sha256 != expected_sha256:
        raise ValueError("RECONCILIATION_TARGET_CHANGED")
    _reopen_xlsx(source_path)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".reconciliation-", suffix=".xlsx", dir=output_path.parent
    )
    temporary = Path(temporary_name)
    published = False
    completed = False
    linked_identity: tuple[int, int] | None = None
    try:
        with os.fdopen(descriptor, "wb") as destination, source_path.open("rb") as input_stream:
            shutil.copyfileobj(input_stream, destination, length=1_048_576)
            destination.flush()
            os.fsync(destination.fileno())
        if _sha256(temporary) != source_sha256 or _sha256(source_path) != source_sha256:
            raise ValueError("RECONCILIATION_TARGET_CHANGED")
        _reopen_xlsx(temporary)
        linked_identity = _file_identity(temporary)
        os.link(temporary, output_path)
        published = True
        output_sha256 = _sha256(output_path)
        if output_sha256 != source_sha256:
            raise ValueError("RECONCILIATION_OUTPUT_VERIFY_FAILED")
        _reopen_xlsx(output_path)
        completed = True
        return output_sha256
    except OSError as error:
        if error.errno == 17:
            raise ValueError("RECONCILIATION_OUTPUT_EXISTS") from None
        raise RuntimeError("RECONCILIATION_NO_CHANGE_PUBLISH_FAILED") from error
    finally:
        if published and not completed and _same_inode(output_path, linked_identity):
            output_path.unlink(missing_ok=True)
        temporary.unlink(missing_ok=True)


def read_reconciliation_target(path, digest: str, stage: str | None):
    """Read A/B/C/D/E/F/J/K while retaining the verified writer schema."""
    source = _materialized(path, f"target:{digest}")
    with open_dual_workbook(WorkbookOpenRequest(source)) as session:
        generic = __import__("report_processor.target_report", fromlist=["read_target_report"])
        stages = enumerate_reconciliation_stages(session)
        selected_stage = resolve_reconciliation_stage(stages, stage)
        report = generic.read_target_report(
            session,
            analyze_workbook_schema(session),
            TargetReportReadRequest(selected_stage=selected_stage),
        )
        bindings = _bindings()
        rows = tuple(_rows(session, selected_stage, bindings))
    if not rows:
        raise ReconciliationTargetScopeError("RECONCILIATION_TARGET_STAGE_EMPTY")
    schema = replace(report.schema, column_bindings=bindings)
    return schema, rows


def category_id(label: str) -> str:
    return "category:" + " ".join(label.casefold().split())


def terminal_index(value: object) -> str | None:
    parsed = extract_document_index(value, allow_loose=True)
    index = parsed.value
    if index is not None and len(index.main) == 4:
        return index.main
    text = str(value or "").strip()
    if re.fullmatch(r"\d{4}", text) and not re.fullmatch(r"(?:19|20)\d{2}", text):
        return text
    return None


def enumerate_reconciliation_stages(session) -> tuple[str, ...]:
    """Return canonical stage identities observed in the fixed target layout."""
    stages: set[str] = set()
    for sheet in session.formula_workbook.worksheets:
        active_index = None
        for row_number in range(1, int(sheet.max_row or 0) + 1):
            index_value = sheet.cell(row_number, 2).value
            if index_value is not None:
                active_index = terminal_index(index_value)
            value = sheet.cell(row_number, 3).value
            if value is None or not str(value).strip():
                continue
            if active_index is None:
                continue
            match = _STAGE_RE.search(str(value).strip())
            stages.add(match.group(1) if match else str(value).strip())
    return tuple(sorted(stages))


def structurally_valid_reconciliation_stages(session, *, maximum: int) -> tuple[str, ...]:
    """Find stages with at least one target row in one workbook pass.

    The criteria mirror ``_rows`` without retaining sheet names, row numbers,
    or other provenance.  ``maximum + 1`` lets callers detect an overlarge
    ambiguous selection without scanning or opening the workbook per stage.
    """

    if not isinstance(maximum, int) or maximum < 1:
        raise ValueError("maximum must be positive")
    stages: set[str] = set()
    for sheet in session.formula_workbook.worksheets:
        active_index = active_stage = None
        for row_number in range(1, int(sheet.max_row or 0) + 1):
            index_value = sheet.cell(row_number, 2).value
            if index_value is not None:
                active_index = terminal_index(index_value)
            raw_stage = sheet.cell(row_number, 3).value
            if raw_stage is not None and str(raw_stage).strip():
                stage_name = str(raw_stage).strip()
                stage_match = _STAGE_RE.search(stage_name)
                active_stage = stage_match.group(1) if stage_match else stage_name
            if (
                active_stage is None
                or active_index is None
                or sheet.cell(row_number, 4).value is None
                or not sheet.cell(row_number, 5).value
            ):
                continue
            stages.add(active_stage)
            if len(stages) > maximum:
                return tuple(sorted(stages))
    return tuple(sorted(stages))


def resolve_reconciliation_stage(stages: tuple[str, ...], requested: str | None) -> str:
    """Resolve only explicit existing stage or exactly one discovered stage."""
    if requested is not None:
        if requested in stages:
            return requested
        raise ReconciliationTargetScopeError("RECONCILIATION_TARGET_STAGE_MISSING")
    if len(stages) == 1:
        return stages[0]
    if not stages:
        raise ReconciliationTargetScopeError("RECONCILIATION_TARGET_STAGE_EMPTY")
    raise ReconciliationTargetScopeError("RECONCILIATION_TARGET_STAGE_AMBIGUOUS")


def writer_calculations(calculations: Iterable[object]) -> tuple[object, ...]:
    """Adapt reconciliation values to the target's two-decimal, million-RUB cells."""
    return tuple(
        replace(
            calculation,
            quantity=_quantize(calculation.quantity),
            cost=_million_rub(calculation.cost),
        )
        for calculation in calculations
    )


def _quantize(value: Decimal | None) -> Decimal | None:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if value is not None else None


def _million_rub(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return (value / Decimal(1_000_000)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _bindings() -> tuple[TargetColumnBinding, ...]:
    columns = (
        (LogicalColumn.OBJECT_CODE, 1, "A"),
        (LogicalColumn.DOCUMENT_INDEX, 2, "B"),
        (LogicalColumn.STAGE, 3, "C"),
        (LogicalColumn.ROW_NUMBER, 4, "D"),
        (LogicalColumn.WORK_NAME, 5, "E"),
        (LogicalColumn.UNIT, 6, "F"),
        (LogicalColumn.CURRENT_PERIOD_QUANTITY, 10, "J"),
        (LogicalColumn.CURRENT_PERIOD_COST, 11, "K"),
    )
    return tuple(
        TargetColumnBinding(key, number, letter, None, "RECONCILIATION_LAYOUT")
        for key, number, letter in columns
    )


def _rows(session, selected_stage: str, bindings):
    formula = session.formula_workbook
    values = session.value_workbook
    trusted = formula_caches_trusted(session.source.local_path)
    for sheet_name in formula.sheetnames:
        formula_sheet, value_sheet = formula[sheet_name], values[sheet_name]
        lexemes = read_sheet_lexemes(session.source.local_path, sheet_name)
        comments = dict(read_sheet_comments(session.source.local_path, sheet_name))
        active_index = active_name = active_stage = None
        for row_number in range(1, int(formula_sheet.max_row or 0) + 1):
            raw_index = formula_sheet.cell(row_number, 2).value
            raw_stage = formula_sheet.cell(row_number, 3).value
            if raw_index is not None:
                active_index = terminal_index(raw_index)
            if raw_stage is not None and str(raw_stage).strip():
                active_name = str(raw_stage).strip()
                stage_match = _STAGE_RE.search(active_name)
                active_stage = stage_match.group(1) if stage_match else active_name
            work_name = formula_sheet.cell(row_number, 5).value
            position = formula_sheet.cell(row_number, 4).value
            if (
                active_stage != selected_stage
                or not active_index
                or not work_name
                or position is None
            ):
                continue
            cells = tuple(
                (
                    binding.logical_column,
                    _cell_snapshot(
                        f"{binding.column_letter}{row_number}",
                        formula_sheet.cell(row_number, binding.column_index),
                        value_sheet.cell(row_number, binding.column_index),
                        lexemes.get(f"{binding.column_letter}{row_number}"),
                        comments.get(f"{binding.column_letter}{row_number}"),
                        trusted,
                    ),
                )
                for binding in bindings
            )
            by_key = dict(cells)
            yield TargetReportRow(
                "ReconciliationTarget-1.0",
                sheet_name,
                SheetType.ADDITIONAL_REPORT,
                row_number,
                str(formula_sheet.cell(row_number, 1).value or "").strip() or None,
                active_name,
                str(position).strip(),
                str(work_name).strip(),
                cells,
                "OK",
                row_kind="OBJECT_PROCESS",
                scope="SELECTED_STAGE",
                document_index_raw=active_index,
                document_index_normalized=active_index,
                stage=active_stage,
                unit=str(formula_sheet.cell(row_number, 6).value or "").strip() or None,
                selected_quantity=_numeric(by_key.get(LogicalColumn.CURRENT_PERIOD_QUANTITY)),
                selected_cost=_numeric(by_key.get(LogicalColumn.CURRENT_PERIOD_COST)),
                writable=trusted,
            )


def _numeric(cell):
    from report_processor.target_report import TargetNumericCell

    if cell is None:
        return None
    return TargetNumericCell(cell.numeric_value, cell.raw_lexeme, "NOT_FORMULA", cell.status)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reopen_xlsx(path: Path) -> None:
    from openpyxl import load_workbook

    try:
        workbook = load_workbook(path, read_only=True, data_only=False, keep_links=True)
        workbook.close()
    except Exception as error:
        raise ValueError("RECONCILIATION_OUTPUT_VERIFY_FAILED") from error


def _same_inode(path: Path, identity: tuple[int, int] | None) -> bool:
    if identity is None:
        return False
    try:
        current = path.stat()
    except OSError:
        return False
    return (current.st_dev, current.st_ino) == identity


def _file_identity(path: Path) -> tuple[int, int]:
    current = path.stat()
    return current.st_dev, current.st_ino
