from __future__ import annotations

import logging
from collections.abc import Iterator

from report_processor.adapters import SourceAdapter, get_source_adapter
from report_processor.excel import DualWorkbookSession
from report_processor.schema import WorksheetSchema

from .config import ExtractionConfig
from .exceptions import AdapterNotAvailableError, ExtractionSchemaError
from .extraction_plan import build_extraction_plan
from .models import CanonicalSourceRow, ExtractionPlan, ExtractionResult
from .result_builders import (
    make_empty_extraction_result,
    resolve_extraction_status,
)
from .row_boundaries import looks_like_repeated_header
from .row_iterator import RowCandidate, iter_source_row_candidates
from .row_mapping import map_row_candidate
from .statuses import (
    AdapterValidationStatus,
    CanonicalRowStatus,
    ExtractionStatus,
    StopReason,
)

LOGGER = logging.getLogger(__name__)


class WorksheetExtractionStream(Iterator[CanonicalSourceRow]):
    def __init__(
        self,
        session: DualWorkbookSession,
        schema: WorksheetSchema,
        adapter: SourceAdapter,
        plan: ExtractionPlan,
        config: ExtractionConfig,
        *,
        document_index: str | None,
        document_period: str | None,
        warnings: tuple[str, ...],
    ) -> None:
        self.session = session
        self.schema = schema
        self.adapter = adapter
        self.plan = plan
        self.config = config
        self.document_index = document_index
        self.document_period = document_period
        self._iterator = iter_source_row_candidates(session, plan, config)
        self._warnings = list(warnings)
        self._skipped_empty = 0
        self._skipped_header = 0
        self._failed = 0
        self._extracted = 0
        self._finished = False

    def __iter__(self) -> WorksheetExtractionStream:
        return self

    def _next_candidate(self) -> RowCandidate:
        try:
            return next(self._iterator)
        except StopIteration:
            self._finished = True
            raise
        except (KeyError, IndexError, ValueError, TypeError, AttributeError) as exc:
            self._warnings.append(f"WORKBOOK_SCAN_FAILED:{type(exc).__name__}:{exc}")
            self._iterator.stop_reason = StopReason.ERROR.value
            self._finished = True
            raise StopIteration from exc

    def __next__(self) -> CanonicalSourceRow:
        if self._finished:
            raise StopIteration
        while True:
            candidate = self._next_candidate()
            if candidate.is_empty and not self.config.include_empty_rows:
                self._skipped_empty += 1
                continue
            if self.config.skip_repeated_headers and looks_like_repeated_header(
                candidate.values,
                self.schema,
            ):
                self._skipped_header += 1
                self._warnings.append(f"REPEATED_HEADER_SKIPPED:{candidate.row_number}")
                LOGGER.debug(
                    "Повторный заголовок пропущен: %s!%s",
                    self.schema.sheet_name,
                    candidate.row_number,
                )
                continue
            try:
                row = map_row_candidate(
                    self.session,
                    self.schema,
                    self.adapter,
                    candidate,
                    document_index=self.document_index,
                    document_period=self.document_period,
                )
            except (TypeError, ValueError, ArithmeticError) as exc:
                self._failed += 1
                self._warnings.append(
                    f"ROW_MAPPING_FAILED:{candidate.row_number}:{type(exc).__name__}:{exc}"
                )
                LOGGER.debug("Ошибка строки %s: %s", candidate.row_number, exc)
                continue
            if row.status == CanonicalRowStatus.ERROR.value:
                self._failed += 1
            if row.warnings:
                LOGGER.debug(
                    "Предупреждения строки %s: %s",
                    candidate.row_number,
                    row.warnings,
                )
            self._extracted += 1
            return row

    def build_result(
        self,
        rows: tuple[CanonicalSourceRow, ...] = (),
    ) -> ExtractionResult:
        if not self._finished:
            raise RuntimeError("Поток листа должен быть полностью исчерпан")
        status = resolve_extraction_status(
            self._iterator,
            extracted=self._extracted,
            failed=self._failed,
            warnings=self._warnings,
        )
        result = ExtractionResult(
            source_file_id=self.session.source_file_id,
            filename=self.session.filename,
            sheet_name=self.schema.sheet_name,
            sheet_type=self.schema.sheet_type,
            rows=rows,
            scanned_row_count=self._iterator.scanned_count,
            extracted_row_count=self._extracted,
            skipped_empty_row_count=self._skipped_empty,
            skipped_header_row_count=self._skipped_header,
            failed_row_count=self._failed,
            start_row=self.plan.data_start_row,
            last_scanned_row=self._iterator.last_scanned_row,
            stop_reason=self._iterator.stop_reason,
            status=status.value,
            warnings=tuple(dict.fromkeys(self._warnings)),
        )
        LOGGER.info(
            "Извлечение завершено: лист=%s, просмотрено=%s, извлечено=%s, stop=%s, status=%s",
            self.schema.sheet_name,
            result.scanned_row_count,
            result.extracted_row_count,
            result.stop_reason,
            result.status,
        )
        return result


def prepare_worksheet_extraction(
    session: DualWorkbookSession,
    schema: WorksheetSchema,
    *,
    document_index: str | None,
    document_period: str | None,
    config: ExtractionConfig,
    adapter: SourceAdapter | None = None,
) -> WorksheetExtractionStream | ExtractionResult:
    LOGGER.info(
        "Начало извлечения: файл=%s, лист=%s, тип=%s, start=%s, max_rows=%s",
        session.filename,
        schema.sheet_name,
        schema.sheet_type.value,
        schema.data_start_row,
        config.max_rows,
    )
    try:
        adapter = adapter or get_source_adapter(schema.sheet_type)
    except AdapterNotAvailableError as exc:
        return make_empty_extraction_result(
            session,
            schema,
            status=ExtractionStatus.ADAPTER_NOT_AVAILABLE,
            warnings=(str(exc),),
        )

    validation = adapter.validate_schema(schema)
    if not validation.valid:
        status = (
            ExtractionStatus.REQUIRED_COLUMNS_MISSING
            if validation.status == AdapterValidationStatus.REQUIRED_COLUMNS_MISSING.value
            else ExtractionStatus.SCHEMA_INVALID
        )
        return make_empty_extraction_result(
            session,
            schema,
            status=status,
            warnings=validation.warnings,
        )
    try:
        plan = build_extraction_plan(session, schema, config)
    except ExtractionSchemaError as exc:
        return make_empty_extraction_result(
            session,
            schema,
            status=ExtractionStatus.SCHEMA_INVALID,
            warnings=(str(exc),),
        )
    return WorksheetExtractionStream(
        session,
        schema,
        adapter,
        plan,
        config,
        document_index=document_index,
        document_period=document_period,
        warnings=tuple((*validation.warnings, *plan.warnings)),
    )
