"""Fail-soft, per-workbook source selection for reconciliation."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openpyxl import load_workbook

from report_processor.extraction.models import CanonicalSourceRow, SourceLocation
from report_processor.identifiers import extract_document_index
from report_processor.metadata.periods import extract_period_from_filename
from report_processor.normalization import NormalizedSourceRow, normalize_training_rows
from report_processor.training_data import prepare_training_data

_UNIT_ALIASES = frozenset({"ед изм", "единица измерения", "единица"})
_HIERARCHY_VALUE_RE = re.compile(r"^\d+(?:\.\d+)+\.?$")


@dataclass(frozen=True, slots=True)
class ReconciliationSourceDescriptor:
    """Safe upload metadata; the private workbook path stays with the adapter."""

    safe_basename: str
    document_index: str | None = None
    document_period: str | None = None

    def __post_init__(self) -> None:
        if not self.safe_basename or self.safe_basename != Path(self.safe_basename).name:
            raise ValueError("safe_basename must be a basename")


def descriptor_from_upload_basename(safe_basename: str) -> ReconciliationSourceDescriptor:
    """Infer optional metadata solely from one validated upload basename."""
    index = extract_document_index(safe_basename).value
    period = extract_period_from_filename(safe_basename).value
    return ReconciliationSourceDescriptor(
        safe_basename=safe_basename,
        document_index=index.normalized if index is not None else None,
        document_period=period.normalized if period is not None else None,
    )


@dataclass(frozen=True, slots=True)
class ReconciliationSourceIssue:
    """Controlled, presentation-safe extraction outcome for one workbook."""

    code: str
    safe_basename: str
    comment: str
    repair_hint: str
    can_continue: bool


@dataclass(frozen=True, slots=True)
class ReconciliationSourceSelection:
    """Private selection summary without paths, sheets, formulas or exceptions."""

    safe_basename: str
    source_type: str
    usable_row_count: int


@dataclass(frozen=True, slots=True)
class ReconciliationSourceBatch:
    """Normalized rows and controlled outcomes from independently read workbooks."""

    rows: tuple[NormalizedSourceRow, ...]
    issues: tuple[ReconciliationSourceIssue, ...]
    selections: tuple[ReconciliationSourceSelection, ...]


class AllReconciliationSourcesUnusableError(ValueError):
    """Every upload failed safely; callers may expose only ``issues``."""

    def __init__(self, issues: tuple[ReconciliationSourceIssue, ...]) -> None:
        super().__init__("RECONCILIATION_SOURCES_UNUSABLE")
        self.issues = issues


def extract_reconciliation_sources(
    workbooks: tuple[tuple[Path, str, ReconciliationSourceDescriptor], ...],
) -> ReconciliationSourceBatch:
    """Choose one usable cumulative source per workbook without cross-file failure."""
    rows: list[NormalizedSourceRow] = []
    issues: list[ReconciliationSourceIssue] = []
    selections: list[ReconciliationSourceSelection] = []
    for path, source_id, descriptor in workbooks:
        try:
            selected = _extract_one(path, source_id, descriptor)
        except Exception:
            issues.append(_issue("WORKBOOK_UNREADABLE", descriptor))
            continue
        if selected is None:
            issues.append(_issue("NO_USABLE_RECONCILIATION_SOURCE", descriptor))
            continue
        source_type, normalized = selected
        rows.extend(normalized)
        selections.append(
            ReconciliationSourceSelection(
                safe_basename=descriptor.safe_basename,
                source_type=source_type,
                usable_row_count=len(normalized),
            )
        )
    batch = ReconciliationSourceBatch(tuple(rows), tuple(issues), tuple(selections))
    if not batch.rows:
        raise AllReconciliationSourcesUnusableError(batch.issues)
    return batch


def _extract_one(
    path: Path, source_id: str, descriptor: ReconciliationSourceDescriptor
) -> tuple[str, tuple[NormalizedSourceRow, ...]] | None:
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        for extractor in (_extract_ks6a_rows, _extract_ks2_rows):
            for sheet in workbook.worksheets:
                canonical = extractor(sheet, source_id, descriptor)
                if canonical:
                    normalized = normalize_training_rows(prepare_training_data(canonical).rows).rows
                    if normalized:
                        return ("ks6a" if extractor is _extract_ks6a_rows else "ks2"), normalized
    finally:
        workbook.close()
    return None


def _extract_ks6a_rows(sheet, source_id: str, descriptor: ReconciliationSourceDescriptor):
    """Read the cumulative pair from a structural multi-row КС-6а header."""
    header_rows = tuple(
        sheet.iter_rows(min_row=1, max_row=min(sheet.max_row, 50), values_only=True)
    )
    work_column = _column_with(header_rows, "наименование этапа")
    unit_column = _unit_column(header_rows)
    cumulative_anchor = _column_with(header_rows, "выполнено за весь период")
    if work_column is None or unit_column is None or cumulative_anchor is None:
        return ()
    quantity_column, cost_column, data_start = _metric_pair(header_rows, cumulative_anchor)
    if quantity_column is None or cost_column is None:
        return ()
    return _canonical_rows(
        sheet,
        source_id,
        descriptor,
        source_type="ks6a",
        start_row=data_start,
        work_column=work_column,
        unit_column=unit_column,
        quantity_column=quantity_column,
        cost_column=cost_column,
        cumulative=True,
    )


def _extract_ks2_rows(sheet, source_id: str, descriptor: ReconciliationSourceDescriptor):
    """Read a structural КС-2 detail table only when its direct metrics are explicit."""
    header_rows = tuple(
        sheet.iter_rows(min_row=1, max_row=min(sheet.max_row, 80), values_only=True)
    )
    work_column = _column_with(header_rows, "наименование работ")
    unit_column = _unit_column(header_rows)
    if work_column is None or unit_column is None:
        return ()
    quantity_column, cost_column, metrics_header_row = _ks2_metric_pair(header_rows)
    if quantity_column is None or cost_column is None:
        return ()
    data_start = (
        max(
            _token_header_row(header_rows, work_column, "наименование работ"),
            _unit_header_row(header_rows, unit_column),
            metrics_header_row,
        )
        + 1
    )
    return _canonical_rows(
        sheet,
        source_id,
        descriptor,
        source_type="ks2",
        start_row=data_start,
        work_column=work_column,
        unit_column=unit_column,
        quantity_column=quantity_column,
        cost_column=cost_column,
        cumulative=False,
    )


def _column_with(rows: tuple[tuple[object, ...], ...], token: str) -> int | None:
    matches: list[tuple[int, int]] = []
    for row_number, row in enumerate(rows, 1):
        for column, value in enumerate(row, 1):
            if token in _text(value):
                matches.append((row_number, column))
    return min((column for _row, column in matches), default=None)


def _unit_column(rows: tuple[tuple[object, ...], ...]) -> int | None:
    """Match only unit-of-measure aliases, never an arbitrary ``ед`` substring."""
    matches = [
        column
        for row in rows
        for column, value in enumerate(row, 1)
        if _header_text(value) in _UNIT_ALIASES
    ]
    return min(matches, default=None)


def _ks2_metric_pair(
    rows: tuple[tuple[object, ...], ...],
) -> tuple[int | None, int | None, int]:
    """Require one explicit quantity / total-cost pair; unit prices are ineligible."""
    for row_number, row in enumerate(rows, 1):
        quantity = _column_within(row, 1, len(row), "количество")
        cost = _column_within(row, 1, len(row), "общая стоимость")
        if quantity is not None and cost is not None and quantity < cost:
            return quantity, cost, row_number
    return None, None, 1


def _token_header_row(rows: tuple[tuple[object, ...], ...], column: int, token: str) -> int:
    return max(
        (number for number, row in enumerate(rows, 1) if token in _text_at(row, column)),
        default=1,
    )


def _unit_header_row(rows: tuple[tuple[object, ...], ...], column: int) -> int:
    return max(
        (
            number
            for number, row in enumerate(rows, 1)
            if _header_text(_value_at(row, column)) in _UNIT_ALIASES
        ),
        default=1,
    )


def _metric_pair(
    rows: tuple[tuple[object, ...], ...], anchor: int
) -> tuple[int | None, int | None, int]:
    for row_number, row in enumerate(rows, 1):
        if _text_at(row, anchor) and "выполнено за весь период" in _text_at(row, anchor):
            for leaf_row in range(row_number + 1, min(row_number + 5, len(rows)) + 1):
                quantity = _column_within(rows[leaf_row - 1], anchor, anchor + 3, "колич")
                cost = _column_within(rows[leaf_row - 1], anchor, anchor + 3, "общая стоимость")
                if quantity is not None and cost is not None:
                    return quantity, cost, leaf_row + 2
    return None, None, 1


def _column_within(row: tuple[object, ...], start: int, end: int, token: str) -> int | None:
    return next(
        (column for column in range(start, end + 1) if token in _text_at(row, column)), None
    )


def _canonical_rows(
    sheet,
    source_id: str,
    descriptor: ReconciliationSourceDescriptor,
    *,
    source_type: str,
    start_row: int,
    work_column: int,
    unit_column: int,
    quantity_column: int,
    cost_column: int,
    cumulative: bool,
) -> tuple[CanonicalSourceRow, ...]:
    rows: list[CanonicalSourceRow] = []
    for row_number, values in enumerate(
        sheet.iter_rows(min_row=start_row, values_only=True), start_row
    ):
        work_name = _text_at(values, work_column)
        unit = _text_at(values, unit_column)
        quantity = _decimal(_value_at(values, quantity_column))
        cost = _decimal(_value_at(values, cost_column))
        if (
            not work_name
            or not unit
            or _HIERARCHY_VALUE_RE.fullmatch(unit) is not None
            or quantity is None
            or cost is None
        ):
            continue
        location = SourceLocation(
            source_file_id=source_id,
            filename=descriptor.safe_basename,
            sheet_name="",
            sheet_type=source_type,
            row_number=row_number,
        )
        rows.append(
            CanonicalSourceRow(
                row_id=f"{source_id}:{source_type}:{row_number}",
                source_type=source_type,
                source_location=location,
                document_index=descriptor.document_index,
                document_period=descriptor.document_period,
                object_code_raw=None,
                object_name_raw=None,
                subobject_code_raw=None,
                subobject_name_raw=None,
                position_code_raw=_text_at(values, 2),
                work_name_raw=work_name,
                unit_raw=unit,
                contract_quantity=None,
                current_period_quantity=None if cumulative else quantity,
                cumulative_quantity=quantity if cumulative else None,
                remaining_quantity=None,
                unit_price=None,
                contract_cost=None,
                current_period_cost=None if cumulative else cost,
                cumulative_cost=cost if cumulative else None,
                total_cost=None,
                basis_code_raw=None,
                drawing_code_raw=_text_at(values, 7),
                cost_type_code_raw=_text_at(values, 3),
                source_values=(),
                status="OK",
                warnings=(),
            )
        )
    return tuple(
        replace(
            row,
            current_period_quantity=row.cumulative_quantity,
            current_period_cost=row.cumulative_cost,
        )
        if cumulative
        else row
        for row in rows
    )


def _value_at(row: tuple[object, ...], column: int) -> object | None:
    return row[column - 1] if column <= len(row) else None


def _text_at(row: tuple[object, ...], column: int) -> str:
    return _text(_value_at(row, column))


def _text(value: object | None) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").casefold().split())


def _header_text(value: object | None) -> str:
    return _text(value).replace(".", "")


def _decimal(value: object | None) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value if value.is_finite() else None
    try:
        parsed = Decimal(str(value).replace("\u00a0", "").replace(" ", "").replace(",", "."))
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def _issue(code: str, descriptor: ReconciliationSourceDescriptor) -> ReconciliationSourceIssue:
    if code == "WORKBOOK_UNREADABLE":
        return ReconciliationSourceIssue(
            code=code,
            safe_basename=descriptor.safe_basename,
            comment="Не удалось безопасно прочитать источник для сверки.",
            repair_hint="Загрузите файл Excel повторно или выберите исправную копию.",
            can_continue=True,
        )
    return ReconciliationSourceIssue(
        code=code,
        safe_basename=descriptor.safe_basename,
        comment="В источнике не найдены пригодные накопительные строки КС-6а или КС-2.",
        repair_hint="Загрузите источник с заполненными строками КС-6а или КС-2.",
        can_continue=True,
    )
