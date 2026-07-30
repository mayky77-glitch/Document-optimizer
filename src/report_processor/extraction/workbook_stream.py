from __future__ import annotations

from collections.abc import Iterator

from report_processor.excel import DualWorkbookSession
from report_processor.schema import SheetType, WorkbookSchema

from .config import ExtractionConfig
from .models import CanonicalSourceRow, ExtractionResult
from .worksheet_stream import WorksheetExtractionStream, prepare_worksheet_extraction

_SUPPORTED_TYPES = {SheetType.KS2, SheetType.KS6A, SheetType.SVVR}


class WorkbookExtractionStream(Iterator[CanonicalSourceRow]):
    def __init__(
        self,
        session: DualWorkbookSession,
        schema: WorkbookSchema,
        *,
        document_index: str | None,
        document_period: str | None,
        config: ExtractionConfig,
    ) -> None:
        self.session = session
        self.schema = schema
        self.document_index = document_index
        self.document_period = document_period
        self.config = config
        self._worksheets = iter(
            item for item in schema.worksheets if item.sheet_type in _SUPPORTED_TYPES
        )
        self._current: WorksheetExtractionStream | None = None
        self._results: list[ExtractionResult] = []
        self._finished = False

    def __iter__(self) -> WorkbookExtractionStream:
        return self

    def _open_next_sheet(self) -> bool:
        while True:
            try:
                worksheet_schema = next(self._worksheets)
            except StopIteration:
                self._finished = True
                return False
            prepared = prepare_worksheet_extraction(
                self.session,
                worksheet_schema,
                document_index=self.document_index,
                document_period=self.document_period,
                config=self.config,
            )
            if isinstance(prepared, ExtractionResult):
                self._results.append(prepared)
                continue
            self._current = prepared
            return True

    def __next__(self) -> CanonicalSourceRow:
        if self._finished:
            raise StopIteration
        while True:
            if self._current is None and not self._open_next_sheet():
                raise StopIteration
            assert self._current is not None
            try:
                return next(self._current)
            except StopIteration:
                self._results.append(self._current.build_result())
                self._current = None

    @property
    def sheet_results(self) -> tuple[ExtractionResult, ...]:
        return tuple(self._results)

    @property
    def finished(self) -> bool:
        return self._finished
