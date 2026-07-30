from __future__ import annotations

from report_processor.domain.exceptions import WorkbookSessionClosedError
from report_processor.domain.statuses import StatusCode

from .models import DualWorkbookSession, WorkbookMetadata, WorksheetMetadata
from .workbook_session import validate_dual_workbook_session


def _defined_names_count(workbook) -> int | None:
    try:
        return len(workbook.defined_names)
    except (AttributeError, TypeError):
        return None


def _external_links_count(workbook) -> int | None:
    links = getattr(workbook, "_external_links", None)
    return len(links) if links is not None else None


def collect_workbook_metadata(session: DualWorkbookSession) -> WorkbookMetadata:
    validate_dual_workbook_session(session)
    workbook = session.formula_workbook
    states = [worksheet.sheet_state for worksheet in workbook.worksheets]
    metadata = WorkbookMetadata(
        filename=session.source.local_path.name,
        extension=session.source.extension,
        size_bytes=session.source.size_bytes,
        macro_enabled=session.format_result.macro_enabled,
        sheet_count=len(workbook.sheetnames),
        sheet_names=tuple(workbook.sheetnames),
        has_hidden_sheets="hidden" in states,
        has_very_hidden_sheets="veryHidden" in states,
        warnings=tuple(session.source.warnings) + tuple(session.format_result.warnings),
        defined_names_count=_defined_names_count(workbook),
        external_links_count=_external_links_count(workbook),
    )
    session.metadata = metadata
    return metadata


def collect_worksheet_metadata(
    session: DualWorkbookSession,
) -> tuple[WorksheetMetadata, ...]:
    if session.closed:
        raise WorkbookSessionClosedError(
            StatusCode.WORKBOOK_SESSION_CLOSED,
            "Workbook-сессия уже закрыта",
        )
    validate_dual_workbook_session(session)
    result: list[WorksheetMetadata] = []
    for index, worksheet in enumerate(session.formula_workbook.worksheets, start=1):
        dimensions: str | None
        try:
            dimensions = worksheet.calculate_dimension()
        except (ValueError, AttributeError):
            dimensions = None
        result.append(
            WorksheetMetadata(
                title=worksheet.title,
                index=index,
                state=worksheet.sheet_state,
                max_row_reported=int(worksheet.max_row or 0),
                max_column_reported=int(worksheet.max_column or 0),
                dimensions_reported=dimensions,
                warnings=("REPORTED_DIMENSIONS_MAY_INCLUDE_FORMATTED_EMPTY_CELLS",),
            )
        )
    return tuple(result)
