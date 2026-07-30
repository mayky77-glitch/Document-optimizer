from __future__ import annotations

from collections.abc import Iterator

from report_processor.adapters import SourceAdapter
from report_processor.excel import DualWorkbookSession
from report_processor.schema import SheetType, WorkbookSchema, WorksheetSchema

from .config import ExtractionConfig
from .exceptions import ExtractionSchemaError
from .models import CanonicalSourceRow, ExtractionResult
from .workbook_stream import WorkbookExtractionStream
from .worksheet_stream import prepare_worksheet_extraction

_SUPPORTED_TYPES = {SheetType.KS2, SheetType.KS6A, SheetType.SVVR}


def iter_worksheet_rows(
    session: DualWorkbookSession,
    schema: WorksheetSchema,
    adapter: SourceAdapter,
    config: ExtractionConfig,
    *,
    document_index: str | None = None,
    document_period: str | None = None,
) -> Iterator[CanonicalSourceRow]:
    prepared = prepare_worksheet_extraction(
        session,
        schema,
        document_index=document_index,
        document_period=document_period,
        config=config,
        adapter=adapter,
    )
    if isinstance(prepared, ExtractionResult):
        raise ExtractionSchemaError(prepared.status)
    return prepared


def extract_worksheet_rows(
    session: DualWorkbookSession,
    schema: WorksheetSchema,
    *,
    document_index: str | None,
    document_period: str | None,
    config: ExtractionConfig | None = None,
) -> ExtractionResult:
    resolved_config = config or ExtractionConfig()
    prepared = prepare_worksheet_extraction(
        session,
        schema,
        document_index=document_index,
        document_period=document_period,
        config=resolved_config,
    )
    if isinstance(prepared, ExtractionResult):
        return prepared
    rows = tuple(prepared)
    return prepared.build_result(rows)


def extract_supported_workbook_rows(
    session: DualWorkbookSession,
    schema: WorkbookSchema,
    *,
    document_index: str | None,
    document_period: str | None,
    config: ExtractionConfig | None = None,
) -> tuple[ExtractionResult, ...]:
    results = []
    for worksheet_schema in schema.worksheets:
        if worksheet_schema.sheet_type not in _SUPPORTED_TYPES:
            continue
        results.append(
            extract_worksheet_rows(
                session,
                worksheet_schema,
                document_index=document_index,
                document_period=document_period,
                config=config,
            )
        )
    return tuple(results)


def create_workbook_extraction_stream(
    session: DualWorkbookSession,
    schema: WorkbookSchema,
    *,
    document_index: str | None,
    document_period: str | None,
    config: ExtractionConfig | None = None,
) -> WorkbookExtractionStream:
    return WorkbookExtractionStream(
        session,
        schema,
        document_index=document_index,
        document_period=document_period,
        config=config or ExtractionConfig(),
    )
