from __future__ import annotations

from report_processor.excel import DualWorkbookSession
from report_processor.schema import WorksheetSchema

from .models import ExtractionResult
from .row_iterator import SourceRowIterator
from .statuses import ExtractionStatus, StopReason


def make_empty_extraction_result(
    session: DualWorkbookSession,
    schema: WorksheetSchema,
    *,
    status: ExtractionStatus,
    warnings: tuple[str, ...],
) -> ExtractionResult:
    return ExtractionResult(
        source_file_id=session.source_file_id,
        filename=session.filename,
        sheet_name=schema.sheet_name,
        sheet_type=schema.sheet_type,
        rows=(),
        scanned_row_count=0,
        extracted_row_count=0,
        skipped_empty_row_count=0,
        skipped_header_row_count=0,
        failed_row_count=0,
        start_row=schema.data_start_row,
        last_scanned_row=None,
        stop_reason=StopReason.ERROR.value,
        status=status.value,
        warnings=warnings,
    )


def resolve_extraction_status(
    iterator: SourceRowIterator,
    *,
    extracted: int,
    failed: int,
    warnings: list[str],
) -> ExtractionStatus:
    if iterator.stop_reason == StopReason.ERROR.value:
        return (
            ExtractionStatus.EXTRACTION_FAILED
            if extracted == 0
            else ExtractionStatus.PARTIAL_SUCCESS
        )
    if extracted == 0:
        return ExtractionStatus.NO_ROWS_EXTRACTED
    if iterator.stop_reason == StopReason.ROW_LIMIT_REACHED.value:
        return ExtractionStatus.ROW_LIMIT_REACHED
    if iterator.stop_reason == StopReason.EMPTY_ROW_LIMIT_REACHED.value:
        return ExtractionStatus.EMPTY_ROW_LIMIT_REACHED
    if failed or warnings:
        return ExtractionStatus.PARTIAL_SUCCESS
    return ExtractionStatus.OK
