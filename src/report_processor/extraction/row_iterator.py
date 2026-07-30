from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from report_processor.excel import DualWorkbookSession

from .cell_values import extract_cell_pair_value
from .config import ExtractionConfig
from .models import ExtractedCellValue, ExtractionPlan
from .row_boundaries import default_key_columns, is_effectively_empty_row
from .statuses import StopReason


@dataclass(frozen=True, slots=True)
class RowCandidate:
    row_number: int
    values: tuple[ExtractedCellValue, ...]
    is_empty: bool


@dataclass(slots=True)
class _ColumnRangeStream:
    start_column: int
    end_column: int
    formula_rows: Iterator[tuple[object, ...]]
    cached_rows: Iterator[tuple[object, ...]]


def _contiguous_ranges(columns: tuple[int, ...]) -> tuple[tuple[int, int], ...]:
    ordered = sorted(set(columns))
    ranges: list[tuple[int, int]] = []
    start = previous = ordered[0]
    for column in ordered[1:]:
        if column == previous + 1:
            previous = column
            continue
        ranges.append((start, previous))
        start = previous = column
    ranges.append((start, previous))
    return tuple(ranges)


class SourceRowIterator(Iterator[RowCandidate]):
    def __init__(
        self,
        session: DualWorkbookSession,
        plan: ExtractionPlan,
        config: ExtractionConfig,
    ) -> None:
        self.session = session
        self.plan = plan
        self.config = config
        self.next_row = plan.data_start_row
        self.scanned_count = 0
        self.last_scanned_row: int | None = None
        self.consecutive_empty_rows = 0
        self.stop_reason = StopReason.REPORTED_END_REACHED.value
        self._finished = False
        logical_columns = tuple(item.logical_column for item in plan.columns)
        self.key_columns = default_key_columns(logical_columns)
        formula_sheet = session.formula_workbook[plan.sheet_name]
        cached_sheet = session.values_workbook[plan.sheet_name]
        ranges = _contiguous_ranges(
            tuple(item.column_index for item in plan.columns if item.column_index is not None)
        )
        self._range_streams = tuple(
            _ColumnRangeStream(
                start_column=start,
                end_column=end,
                formula_rows=iter(
                    formula_sheet.iter_rows(
                        min_row=plan.data_start_row,
                        max_row=plan.max_end_row,
                        min_col=start,
                        max_col=end,
                    )
                ),
                cached_rows=iter(
                    cached_sheet.iter_rows(
                        min_row=plan.data_start_row,
                        max_row=plan.max_end_row,
                        min_col=start,
                        max_col=end,
                    )
                ),
            )
            for start, end in ranges
        )

    def __iter__(self) -> SourceRowIterator:
        return self

    def _mark_stream_error(self, message: str, exc: BaseException) -> None:
        self.stop_reason = StopReason.ERROR.value
        self._finished = True
        raise ValueError(message) from exc

    def _next_workbook_cells(
        self,
    ) -> tuple[dict[int, object], dict[int, object]]:
        formula_cells: dict[int, object] = {}
        cached_cells: dict[int, object] = {}
        for range_index, stream in enumerate(self._range_streams):
            try:
                formula_row = tuple(next(stream.formula_rows))
            except StopIteration as exc:
                if range_index == 0:
                    self.stop_reason = StopReason.REPORTED_END_REACHED.value
                    self._finished = True
                    raise
                self._mark_stream_error(
                    "Formula worksheet column ranges diverged",
                    exc,
                )
            try:
                cached_row = tuple(next(stream.cached_rows))
            except StopIteration as exc:
                self._mark_stream_error(
                    "Dual workbook row iterators diverged",
                    exc,
                )
            expected_width = stream.end_column - stream.start_column + 1
            if len(formula_row) != expected_width or len(cached_row) != expected_width:
                self._mark_stream_error(
                    "Worksheet row width differs from requested column range",
                    ValueError("row width mismatch"),
                )
            for offset, cell in enumerate(formula_row):
                formula_cells[stream.start_column + offset] = cell
            for offset, cell in enumerate(cached_row):
                cached_cells[stream.start_column + offset] = cell
        return formula_cells, cached_cells

    def __next__(self) -> RowCandidate:
        if self._finished:
            raise StopIteration
        if self.scanned_count >= self.config.max_rows:
            self.stop_reason = StopReason.ROW_LIMIT_REACHED.value
            self._finished = True
            raise StopIteration
        if self.next_row > self.plan.max_end_row:
            self.stop_reason = (
                StopReason.ROW_LIMIT_REACHED.value
                if self.scanned_count >= self.config.max_rows
                else StopReason.REPORTED_END_REACHED.value
            )
            self._finished = True
            raise StopIteration

        row_number = self.next_row
        formula_cells, cached_cells = self._next_workbook_cells()
        values = tuple(
            extract_cell_pair_value(
                self.session,
                sheet_name=self.plan.sheet_name,
                row_number=row_number,
                column_resolution=column,
                formula_cell=formula_cells[column.column_index],
                cached_cell=cached_cells[column.column_index],
                sheet_type=self.plan.sheet_type,
            )
            for column in self.plan.columns
        )

        self.next_row += 1
        self.scanned_count += 1
        self.last_scanned_row = row_number
        is_empty = is_effectively_empty_row(
            values,
            key_columns=self.key_columns,
            include_formula_without_cache=self.config.include_formula_without_cache,
        )
        if is_empty:
            self.consecutive_empty_rows += 1
        else:
            self.consecutive_empty_rows = 0

        candidate = RowCandidate(row_number=row_number, values=values, is_empty=is_empty)
        if self.consecutive_empty_rows >= self.config.max_consecutive_empty_rows:
            self.stop_reason = StopReason.EMPTY_ROW_LIMIT_REACHED.value
            self._finished = True
        return candidate


def iter_source_row_candidates(
    session: DualWorkbookSession,
    plan: ExtractionPlan,
    config: ExtractionConfig,
) -> SourceRowIterator:
    return SourceRowIterator(session, plan, config)


def iter_source_row_numbers(
    session: DualWorkbookSession,
    plan: ExtractionPlan,
    config: ExtractionConfig,
) -> Iterator[int]:
    for candidate in iter_source_row_candidates(session, plan, config):
        yield candidate.row_number
