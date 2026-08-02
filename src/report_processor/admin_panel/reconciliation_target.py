"""Adapter for the documented additional-report reconciliation layout."""

from __future__ import annotations

import re
from dataclasses import replace

from report_processor.excel import WorkbookOpenRequest, open_dual_workbook
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

_INDEX_RE = re.compile(r"(\d{4})(?!.*\d)")
_STAGE_RE = re.compile(r"этап\s*([0-9]+(?:\.[0-9]+)*)", re.IGNORECASE)


def read_reconciliation_target(path, digest: str, stage: str):
    """Read A/B/C/D/E/F/J/K while retaining the verified writer schema."""
    source = _materialized(path, f"target:{digest}")
    with open_dual_workbook(WorkbookOpenRequest(source)) as session:
        generic = __import__("report_processor.target_report", fromlist=["read_target_report"])
        report = generic.read_target_report(
            session, analyze_workbook_schema(session), TargetReportReadRequest(selected_stage=stage)
        )
        bindings = _bindings()
        rows = tuple(_rows(session, stage, bindings))
    schema = replace(report.schema, column_bindings=bindings)
    return schema, rows


def category_id(label: str) -> str:
    return "category:" + " ".join(label.casefold().split())


def terminal_index(value: object) -> str | None:
    match = _INDEX_RE.search(str(value or ""))
    return match.group(1) if match else None


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
