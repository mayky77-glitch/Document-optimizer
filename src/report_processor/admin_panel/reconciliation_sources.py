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
_BARE_DOCUMENT_INDEX_RE = re.compile(r"(?<!\d)(\d{4})(?!\d)")
_YEAR_RE = re.compile(r"(?:19|20)\d{2}")


class FormulaCacheUnavailableError(ValueError):
    """An otherwise usable source metric cannot be verified from its cache."""


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
        document_index=(
            index.normalized if index is not None else document_index_from_basename(safe_basename)
        ),
        document_period=period.normalized if period is not None else None,
    )


def document_index_from_basename(safe_basename: str) -> str | None:
    """Return a strict index or one unambiguous non-year four-digit main index."""
    parsed = extract_document_index(safe_basename).value
    if parsed is not None:
        return parsed.main
    candidates = tuple(dict.fromkeys(_BARE_DOCUMENT_INDEX_RE.findall(Path(safe_basename).stem)))
    non_year = tuple(value for value in candidates if _YEAR_RE.fullmatch(value) is None)
    return non_year[0] if len(non_year) == 1 else None


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
    *,
    require_document_index: bool = False,
) -> ReconciliationSourceBatch:
    """Choose one usable cumulative source per workbook without cross-file failure."""
    rows: list[NormalizedSourceRow] = []
    issues: list[ReconciliationSourceIssue] = []
    selections: list[ReconciliationSourceSelection] = []
    for path, source_id, descriptor in workbooks:
        if require_document_index and not _has_usable_document_index(descriptor):
            issues.append(_issue("DOCUMENT_INDEX_MISSING", descriptor))
            continue
        try:
            selected = _extract_one(path, source_id, descriptor)
        except FormulaCacheUnavailableError:
            issues.append(_issue("FORMULA_CACHE_UNAVAILABLE", descriptor))
            continue
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
    formulas = load_workbook(path, read_only=True, data_only=False)
    try:
        for extractor in (_extract_ks6a_rows, _extract_ks2_rows):
            for sheet in workbook.worksheets:
                canonical = extractor(sheet, formulas[sheet.title], source_id, descriptor)
                if canonical:
                    normalized = normalize_training_rows(prepare_training_data(canonical).rows).rows
                    if normalized:
                        return ("ks6a" if extractor is _extract_ks6a_rows else "ks2"), normalized
    finally:
        formulas.close()
        workbook.close()
    return None


def _extract_ks6a_rows(
    sheet, formula_sheet, source_id: str, descriptor: ReconciliationSourceDescriptor
):
    """Read the cumulative pair from a structural multi-row КС-6а header."""
    header_rows = tuple(
        sheet.iter_rows(min_row=1, max_row=min(sheet.max_row, 50), values_only=True)
    )
    work_column = _role_column(header_rows, "work")
    unit_column = _unit_column(header_rows)
    cumulative_anchor = _role_column(header_rows, "cumulative")
    if work_column is None or unit_column is None or cumulative_anchor is None:
        return ()
    quantity_column, cost_column, header_end = _metric_pair(header_rows, cumulative_anchor)
    if quantity_column is None or cost_column is None:
        return ()
    return _canonical_rows(
        sheet,
        source_id,
        descriptor,
        source_type="ks6a",
        start_row=_detail_start(
            sheet,
            formula_sheet,
            header_end,
            work_column,
            unit_column,
            quantity_column,
            cost_column,
        ),
        work_column=work_column,
        unit_column=unit_column,
        quantity_column=quantity_column,
        cost_column=cost_column,
        cumulative=True,
        formula_sheet=formula_sheet,
    )


def _extract_ks2_rows(
    sheet, formula_sheet, source_id: str, descriptor: ReconciliationSourceDescriptor
):
    """Read a structural КС-2 detail table only when its direct metrics are explicit."""
    header_rows = tuple(
        sheet.iter_rows(min_row=1, max_row=min(sheet.max_row, 80), values_only=True)
    )
    work_column = _role_column(header_rows, "work")
    unit_column = _unit_column(header_rows)
    if work_column is None or unit_column is None:
        return ()
    quantity_column, cost_column, metrics_header_row = _ks2_metric_pair(header_rows)
    if quantity_column is None or cost_column is None:
        return ()
    header_end = max(
        _role_header_row(header_rows, work_column, "work"),
        _unit_header_row(header_rows, unit_column),
        metrics_header_row,
    )
    data_start = _detail_start(
        sheet,
        formula_sheet,
        header_end,
        work_column,
        unit_column,
        quantity_column,
        cost_column,
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
        formula_sheet=formula_sheet,
    )


def _column_with(rows: tuple[tuple[object, ...], ...], token: str) -> int | None:
    matches: list[tuple[int, int]] = []
    for row_number, row in enumerate(rows, 1):
        for column, value in enumerate(row, 1):
            if token in _text(value):
                matches.append((row_number, column))
    return min((column for _row, column in matches), default=None)


def _header_path(rows: tuple[tuple[object, ...], ...], row_number: int, column: int) -> str:
    """Join all non-empty ancestor labels in a variable-depth header column."""
    return " ".join(
        _text_at(rows[number - 1], column)
        for number in range(1, row_number + 1)
        if _text_at(rows[number - 1], column)
    )


def _role_text(value: str, role: str) -> bool:
    if role == "work":
        return "наименован" in value and ("работ" in value or "этап" in value)
    if role == "cumulative":
        return "выполн" in value and ("весь" in value or "нараст" in value)
    return False


def _role_column(rows: tuple[tuple[object, ...], ...], role: str) -> int | None:
    matches = [
        column
        for row_number, row in enumerate(rows, 1)
        for column in range(1, len(row) + 1)
        if _role_text(_header_path(rows, row_number, column), role)
    ]
    return min(matches, default=None)


def _role_header_row(rows: tuple[tuple[object, ...], ...], column: int, role: str) -> int:
    return max(
        (
            number
            for number in range(1, len(rows) + 1)
            if _role_text(_text_at(rows[number - 1], column), role)
        ),
        default=1,
    )


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
    for row_number, _row in enumerate(rows, 1):
        if _role_text(_header_path(rows, row_number, anchor), "cumulative"):
            for leaf_row in range(row_number + 1, min(row_number + 5, len(rows)) + 1):
                quantity = _column_within(rows[leaf_row - 1], anchor, anchor + 3, "колич")
                cost = _column_within(rows[leaf_row - 1], anchor, anchor + 3, "общая стоимость")
                if quantity is not None and cost is not None:
                    return quantity, cost, leaf_row
    return None, None, 1


def _detail_start(
    sheet,
    formula_sheet,
    header_end: int,
    work_column: int,
    unit_column: int,
    quantity_column: int,
    cost_column: int,
) -> int:
    """Find first semantic detail row; never assume a fixed header depth."""
    values_rows = sheet.iter_rows(min_row=header_end + 1, values_only=True)
    for row_number, values in enumerate(values_rows, header_end + 1):
        work, unit = _text_at(values, work_column), _text_at(values, unit_column)
        formulas_present = (
            formula_sheet.cell(row_number, quantity_column).data_type == "f"
            or formula_sheet.cell(row_number, cost_column).data_type == "f"
        )
        if (
            work
            and unit
            and _HIERARCHY_VALUE_RE.fullmatch(unit) is None
            and (
                formulas_present
                or (
                    _decimal(_value_at(values, quantity_column)) is not None
                    and _decimal(_value_at(values, cost_column)) is not None
                )
            )
        ):
            return row_number
    return header_end + 1


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
    formula_sheet=None,
) -> tuple[CanonicalSourceRow, ...]:
    rows: list[CanonicalSourceRow] = []
    for row_number, values in enumerate(
        sheet.iter_rows(min_row=start_row, values_only=True), start_row
    ):
        work_name = _text_at(values, work_column)
        unit = _text_at(values, unit_column)
        quantity = _decimal(_value_at(values, quantity_column))
        cost = _decimal(_value_at(values, cost_column))
        if formula_sheet is not None:
            for column, cached in ((quantity_column, quantity), (cost_column, cost)):
                formula_cell = formula_sheet.cell(row_number, column)
                if formula_cell.data_type == "f" and cached is None:
                    raise FormulaCacheUnavailableError("FORMULA_CACHE_UNAVAILABLE")
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
            sheet_name=sheet.title,
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
    if code == "DOCUMENT_INDEX_MISSING":
        return ReconciliationSourceIssue(
            code=code,
            safe_basename=descriptor.safe_basename,
            comment="В имени файла не найден четырёхзначный индекс документа.",
            repair_hint=(
                "Добавьте один индекс из целевого отчёта, например «1234», "
                "в имя файла и загрузите его снова."
            ),
            can_continue=True,
        )
    if code == "WORKBOOK_UNREADABLE":
        return ReconciliationSourceIssue(
            code=code,
            safe_basename=descriptor.safe_basename,
            comment="Не удалось безопасно прочитать источник для сверки.",
            repair_hint="Загрузите файл Excel повторно или выберите исправную копию.",
            can_continue=True,
        )
    if code == "FORMULA_CACHE_UNAVAILABLE":
        return ReconciliationSourceIssue(
            code=code,
            safe_basename=descriptor.safe_basename,
            comment="В расчётных ячейках источника нет проверяемых значений формул.",
            repair_hint="Пересчитайте книгу в Excel и загрузите сохранённую копию.",
            can_continue=True,
        )
    return ReconciliationSourceIssue(
        code=code,
        safe_basename=descriptor.safe_basename,
        comment="В источнике не найдены пригодные накопительные строки КС-6а или КС-2.",
        repair_hint="Загрузите источник с заполненными строками КС-6а или КС-2.",
        can_continue=True,
    )


def _has_usable_document_index(descriptor: ReconciliationSourceDescriptor) -> bool:
    raw = descriptor.document_index or ""
    parsed = extract_document_index(raw).value
    main = parsed.main if parsed is not None else raw
    return re.fullmatch(r"\d{4}", main) is not None
