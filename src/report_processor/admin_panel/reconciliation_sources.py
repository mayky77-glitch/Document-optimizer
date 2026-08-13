"""Fail-soft, per-workbook source selection for reconciliation."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openpyxl import load_workbook

from report_processor.extraction.models import CanonicalSourceRow, SourceLocation
from report_processor.metadata.periods import extract_period_from_filename
from report_processor.normalization import NormalizedSourceRow, normalize_training_rows
from report_processor.training_data import prepare_training_data

from .reconciliation_identity import resolve_source_identity, source_basename_identities

_UNIT_ALIASES = frozenset({"ед изм", "единица измерения", "единица"})
_HIERARCHY_VALUE_RE = re.compile(r"^\d+(?:\.\d+)+\.?$")


class FormulaCacheUnavailableError(ValueError):
    """An otherwise usable source metric cannot be verified from its cache."""


class SourceLayoutAmbiguousError(ValueError):
    """More than one structurally viable source layout exists."""


@dataclass(frozen=True, slots=True)
class ReconciliationSourceDescriptor:
    """Safe upload metadata; the private workbook path stays with the adapter."""

    safe_basename: str
    document_index: str | None = None
    document_period: str | None = None
    document_index_candidates: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.safe_basename or self.safe_basename != Path(self.safe_basename).name:
            raise ValueError("safe_basename must be a basename")


@dataclass(frozen=True, slots=True)
class _HeaderGraph:
    """Bounded header cells with real merged-cell propagation and parent spans."""

    rows: tuple[tuple[object, ...], ...]
    spans: dict[tuple[int, int], tuple[int, int, int, int]]

    def parent_span(self, row: int, column: int) -> tuple[int, int]:
        _top, left, _bottom, right = self.spans.get((row, column), (row, column, row, column))
        return left, right


def descriptor_from_upload_basename(safe_basename: str) -> ReconciliationSourceDescriptor:
    """Infer optional metadata solely from one validated upload basename."""
    period = extract_period_from_filename(safe_basename).value
    candidates = source_basename_identities(safe_basename)
    return ReconciliationSourceDescriptor(
        safe_basename=safe_basename,
        document_index=candidates[0] if len(candidates) == 1 else None,
        document_period=period.normalized if period is not None else None,
        document_index_candidates=candidates,
    )


def document_index_from_basename(safe_basename: str) -> str | None:
    """Return an unambiguous bounded filename identity."""
    candidates = source_basename_identities(safe_basename)
    return candidates[0] if len(candidates) == 1 else None


def resolve_descriptor_identity(
    descriptor: ReconciliationSourceDescriptor, target_identities: set[str] | frozenset[str]
) -> ReconciliationSourceDescriptor:
    """Bind a source basename only to one terminal identity in the selected stage."""
    candidates = descriptor.document_index_candidates or (
        (descriptor.document_index,) if descriptor.document_index else ()
    )
    identity = resolve_source_identity(candidates, target_identities)
    return replace(descriptor, document_index=identity)


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
    terminal_identities: tuple[tuple[str, str], ...] = ()


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
    identities: list[tuple[str, str]] = []
    for path, source_id, descriptor in workbooks:
        if require_document_index and not _has_usable_document_index(descriptor):
            issues.append(_issue("DOCUMENT_INDEX_MISSING", descriptor))
            continue
        try:
            selected = _extract_one(path, source_id, descriptor)
        except FormulaCacheUnavailableError:
            issues.append(_issue("FORMULA_CACHE_UNAVAILABLE", descriptor))
            continue
        except SourceLayoutAmbiguousError:
            issues.append(_issue("SOURCE_LAYOUT_AMBIGUOUS", descriptor))
            continue
        except Exception:
            issues.append(_issue("WORKBOOK_UNREADABLE", descriptor))
            continue
        if selected is None:
            issues.append(_issue("NO_USABLE_RECONCILIATION_SOURCE", descriptor))
            continue
        source_type, normalized = selected
        rows.extend(normalized)
        if descriptor.document_index is not None:
            identities.append((source_id, descriptor.document_index))
        selections.append(
            ReconciliationSourceSelection(
                safe_basename=descriptor.safe_basename,
                source_type=source_type,
                usable_row_count=len(normalized),
            )
        )
    batch = ReconciliationSourceBatch(
        tuple(rows), tuple(issues), tuple(selections), tuple(sorted(identities))
    )
    if not batch.rows:
        raise AllReconciliationSourcesUnusableError(batch.issues)
    return batch


def _extract_one(
    path: Path, source_id: str, descriptor: ReconciliationSourceDescriptor
) -> tuple[str, tuple[NormalizedSourceRow, ...]] | None:
    # Candidate enumeration needs repeated, deterministic passes over each sheet.
    workbook = load_workbook(path, read_only=False, data_only=True)
    formulas = load_workbook(path, read_only=False, data_only=False)
    try:
        candidates: list[tuple[str, str, tuple[NormalizedSourceRow, ...]]] = []
        for sheet in workbook.worksheets:
            for extractor, source_type in (
                (_extract_ks6a_rows, "ks6a"),
                (_extract_ks2_rows, "ks2"),
            ):
                canonical = extractor(sheet, formulas[sheet.title], source_id, descriptor)
                if canonical:
                    normalized = normalize_training_rows(prepare_training_data(canonical).rows).rows
                    if normalized:
                        candidates.append((source_type, sheet.title, normalized))
        cumulative = [candidate for candidate in candidates if candidate[0] == "ks6a"]
        viable = cumulative or candidates
        if len(viable) > 1:
            raise SourceLayoutAmbiguousError("SOURCE_LAYOUT_AMBIGUOUS")
        if viable:
            source_type, _sheet_name, normalized = viable[0]
            return source_type, normalized
    finally:
        formulas.close()
        workbook.close()
    return None


def _extract_ks6a_rows(
    sheet, formula_sheet, source_id: str, descriptor: ReconciliationSourceDescriptor
):
    """Read the cumulative pair from a structural multi-row КС-6а header."""
    header_rows = _header_graph(sheet, maximum=50)
    candidates = []
    for work_column, unit_column, anchor in _layout_columns(header_rows, cumulative=True):
        for quantity_column, cost_column, header_end in _metric_pairs_for_anchor(
            header_rows, anchor
        ):
            rows = _canonical_rows(
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
            if rows:
                span = _parent_span_for_anchor(header_rows, anchor)
                if span is None:
                    continue
                parent_top, parent_left, _parent_bottom, parent_right = span
                candidates.append(
                    (
                        (
                            work_column,
                            unit_column,
                            parent_top,
                            parent_left,
                            parent_right,
                            quantity_column,
                            cost_column,
                            header_end,
                        ),
                        rows,
                    )
                )
    return _unique_layout_rows(candidates)


def _extract_ks2_rows(
    sheet, formula_sheet, source_id: str, descriptor: ReconciliationSourceDescriptor
):
    """Read a structural КС-2 detail table only when its direct metrics are explicit."""
    header_rows = _header_graph(sheet, maximum=80)
    candidates = []
    for work_column, unit_column, _anchor in _layout_columns(header_rows, cumulative=False):
        for quantity_column, cost_column, metric_row in _metric_pairs_for_row(header_rows):
            header_end = max(
                _role_header_row(header_rows, work_column, "work"),
                _unit_header_row(header_rows, unit_column),
                metric_row,
            )
            rows = _canonical_rows(
                sheet,
                source_id,
                descriptor,
                source_type="ks2",
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
                cumulative=False,
                formula_sheet=formula_sheet,
            )
            if rows:
                candidates.append(
                    ((work_column, unit_column, quantity_column, cost_column, metric_row), rows)
                )
    return _unique_layout_rows(candidates)


def _header_graph(sheet, *, maximum: int) -> _HeaderGraph:
    """Materialize only bounded header cells, filling each merged range from its top-left."""
    max_row = min(int(sheet.max_row or 0), maximum)
    max_column = int(sheet.max_column or 0)
    values = [
        [sheet.cell(row, column).value for column in range(1, max_column + 1)]
        for row in range(1, max_row + 1)
    ]
    spans: dict[tuple[int, int], tuple[int, int, int, int]] = {}
    for merged in sheet.merged_cells.ranges:
        if merged.min_row > max_row or merged.min_col > max_column:
            continue
        top, left = merged.min_row, merged.min_col
        bottom, right = min(merged.max_row, max_row), min(merged.max_col, max_column)
        value = sheet.cell(top, left).value
        for row in range(top, bottom + 1):
            for column in range(left, right + 1):
                values[row - 1][column - 1] = value
                spans[(row, column)] = (top, left, bottom, right)
    return _HeaderGraph(tuple(tuple(row) for row in values), spans)


def _rows(header: _HeaderGraph | tuple[tuple[object, ...], ...]):
    return header.rows if isinstance(header, _HeaderGraph) else header


def _layout_columns(header, *, cumulative: bool) -> list[tuple[int, int, int | None]]:
    rows = _rows(header)
    work = _role_columns(rows, "work")
    units = _unit_columns(rows)
    anchors = _role_columns(rows, "cumulative") if cumulative else [None]
    return [
        (work_column, unit_column, anchor)
        for work_column in work
        for unit_column in units
        for anchor in anchors
        if work_column != unit_column
    ]


def _unique_layout_rows(candidates):
    # Merged parent labels legitimately nominate every covered child column;
    # normalize those candidates to their parent-left physical boundary.
    unique = {key: rows for key, rows in candidates}
    if len(unique) > 1:
        raise SourceLayoutAmbiguousError("SOURCE_LAYOUT_AMBIGUOUS")
    return next(iter(unique.values()), ())


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
        return any(stem in value for stem in ("наименован", "описан", "вид работ"))
    if role == "cumulative":
        return ("выполн" in value or "освоен" in value) and (
            "весь" in value or "нараст" in value or "итог" in value
        )
    return False


def _role_column(rows: tuple[tuple[object, ...], ...], role: str) -> int | None:
    columns = _role_columns(rows, role)
    return columns[0] if len(columns) == 1 else None


def _role_columns(rows: tuple[tuple[object, ...], ...], role: str) -> list[int]:
    matches = [
        column
        for row_number, row in enumerate(rows, 1)
        for column in range(1, len(row) + 1)
        if _role_text(_header_path(rows, row_number, column), role)
    ]
    return sorted(set(matches))


def _role_header_row(rows: tuple[tuple[object, ...], ...], column: int, role: str) -> int:
    rows = _rows(rows)
    return min(
        (
            number
            for number in range(1, len(rows) + 1)
            if _role_text(_header_path(rows, number, column), role)
        ),
        default=1,
    )


def _unit_column(rows: tuple[tuple[object, ...], ...]) -> int | None:
    """Find one semantic unit column across variable hierarchical headers."""
    matches = _unit_columns(rows)
    return matches[0] if len(matches) == 1 else None


def _unit_columns(rows: tuple[tuple[object, ...], ...]) -> list[int]:
    matches = [
        column
        for row_number, row in enumerate(rows, 1)
        for column in range(1, len(row) + 1)
        if _unit_text(_header_path(rows, row_number, column))
    ]
    return sorted(set(matches))


def _unit_text(value: str) -> bool:
    compact = _header_text(value)
    return compact in _UNIT_ALIASES or ("ед" in compact and "измер" in compact) or "unit" in compact


def _ks2_metric_pair(
    rows: tuple[tuple[object, ...], ...],
) -> tuple[int | None, int | None, int]:
    """Require one explicit quantity / total-cost pair; unit prices are ineligible."""
    pairs = _metric_pairs_for_row(rows)
    if len(pairs) == 1:
        return pairs[0]
    if len(pairs) > 1:
        raise SourceLayoutAmbiguousError("SOURCE_LAYOUT_AMBIGUOUS")
    return None, None, 1


def _metric_pairs_for_row(header) -> list[tuple[int, int, int]]:
    rows = _rows(header)
    return [
        (quantity, cost, row_number)
        for row_number, row in enumerate(rows, 1)
        for quantity, cost in _metric_pairs(row, 1, len(row))
    ]


def _token_header_row(rows: tuple[tuple[object, ...], ...], column: int, token: str) -> int:
    return max(
        (number for number, row in enumerate(rows, 1) if token in _text_at(row, column)),
        default=1,
    )


def _unit_header_row(rows: tuple[tuple[object, ...], ...], column: int) -> int:
    rows = _rows(rows)
    return max(
        (number for number, row in enumerate(rows, 1) if _unit_text(_text_at(row, column))),
        default=1,
    )


def _metric_pair(
    rows: tuple[tuple[object, ...], ...], anchor: int
) -> tuple[int | None, int | None, int]:
    candidates = _metric_pairs_for_anchor(rows, anchor)
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise SourceLayoutAmbiguousError("SOURCE_LAYOUT_AMBIGUOUS")
    return None, None, 1


def _metric_pairs_for_anchor(header, anchor: int) -> list[tuple[int, int, int]]:
    rows = _rows(header)
    candidates = []
    for row_number, _row in enumerate(rows, 1):
        if _role_text(_header_path(rows, row_number, anchor), "cumulative"):
            span = _parent_span_for_anchor(header, anchor)
            if span is None:
                continue
            _top, start, _bottom, end = span
            for leaf_row in range(row_number + 1, min(row_number + 5, len(rows)) + 1):
                pairs = _metric_pairs(rows[leaf_row - 1], start, end)
                candidates.extend((quantity, cost, leaf_row) for quantity, cost in pairs)
    return candidates


def _parent_span_for_anchor(header, anchor: int) -> tuple[int, int, int, int] | None:
    if not isinstance(header, _HeaderGraph):
        return None
    spans = {span for (row, column), span in header.spans.items() if column == anchor}
    return next(iter(spans)) if len(spans) == 1 else None


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


def _metric_pairs(row: tuple[object, ...], start: int, end: int) -> list[tuple[int, int]]:
    quantities = [
        column
        for column in range(start, min(end, len(row)) + 1)
        if any(stem in _text_at(row, column) for stem in ("колич", "объем", "объём"))
    ]
    costs = [
        column
        for column in range(start, min(end, len(row)) + 1)
        if _cost_text(_text_at(row, column))
    ]
    return [(quantity, cost) for quantity in quantities for cost in costs if cost == quantity + 1]


def _cost_text(value: str) -> bool:
    return ("стоим" in value or "сумм" in value or "затрат" in value) and not (
        "единиц" in value or "цен" in value
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
        quantity_formula = (
            formula_sheet is not None
            and formula_sheet.cell(row_number, quantity_column).data_type == "f"
        )
        cost_formula = (
            formula_sheet is not None
            and formula_sheet.cell(row_number, cost_column).data_type == "f"
        )
        if (
            not work_name
            or not unit
            or _HIERARCHY_VALUE_RE.fullmatch(unit) is not None
            or (quantity is None and not quantity_formula)
            or (cost is None and not cost_formula)
        ):
            continue
        if formula_sheet is not None:
            for column, cached in ((quantity_column, quantity), (cost_column, cost)):
                formula_cell = formula_sheet.cell(row_number, column)
                if formula_cell.data_type == "f" and cached is None:
                    raise FormulaCacheUnavailableError("FORMULA_CACHE_UNAVAILABLE")
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
    normalized = unicodedata.normalize("NFKC", str(value or "")).replace("\u00a0", " ")
    return " ".join(re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE).casefold().split())


def _header_text(value: object | None) -> str:
    return _text(value)


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
    if code == "SOURCE_LAYOUT_AMBIGUOUS":
        return ReconciliationSourceIssue(
            code=code,
            safe_basename=descriptor.safe_basename,
            comment="В источнике найдено несколько несовместимых табличных структур.",
            repair_hint="Оставьте один однозначный лист с таблицей и загрузите книгу снова.",
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
    return re.fullmatch(r"\d{4}", raw) is not None
