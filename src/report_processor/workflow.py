from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path

from report_processor.domain.exceptions import UnsupportedExcelFormatError
from report_processor.domain.statuses import StatusCode
from report_processor.excel.formats import detect_excel_format
from report_processor.excel.models import DualWorkbookSession, WorkbookOpenRequest
from report_processor.excel.workbook_metadata import collect_workbook_metadata
from report_processor.excel.workbook_session import (
    open_dual_workbook,
    validate_dual_workbook_session,
)
from report_processor.materialization.materializer import materialize_source
from report_processor.materialization.models import MaterializationRequest
from report_processor.materialization.workspace import TemporaryWorkspace
from report_processor.processing import (
    ProcessingResult,
    ProcessReportRequest,
)
from report_processor.processing import (
    process_report as _process_report,
)
from report_processor.processing import (
    process_reports as _process_reports,
)
from report_processor.selection.models import SourceCandidate

LOGGER = logging.getLogger(__name__)


def process_report(request: ProcessReportRequest) -> ProcessingResult:
    """Run the frozen Block 17 single-report controller."""

    return _process_report(request)


def process_reports(requests: Iterable[ProcessReportRequest]) -> tuple[ProcessingResult, ...]:
    """Run requests in deterministic caller order with per-request isolation."""

    return _process_reports(requests)


@contextmanager
def prepared_workbook_session(
    candidate: SourceCandidate,
    *,
    workspace_root: Path | None = None,
    max_file_size_bytes: int = 2 * 1024**3,
) -> Iterator[DualWorkbookSession]:
    request = MaterializationRequest(
        candidate=candidate,
        workspace_root=workspace_root,
        max_file_size_bytes=max_file_size_bytes,
    )
    with ExitStack() as stack:
        workspace = None
        if candidate.entry.is_archive_entry:
            workspace = stack.enter_context(TemporaryWorkspace(workspace_root))

        source = materialize_source(request, workspace=workspace)
        format_result = detect_excel_format(source.local_path)
        if not format_result.supported:
            status = (
                StatusCode.INVALID_XLSX_CONTAINER
                if StatusCode.INVALID_XLSX_CONTAINER.value in format_result.warnings
                else StatusCode.UNSUPPORTED_EXCEL_FORMAT
            )
            raise UnsupportedExcelFormatError(
                status,
                f"Формат {format_result.extension or '<none>'} не поддерживается",
            )

        session = stack.enter_context(open_dual_workbook(WorkbookOpenRequest(source=source)))
        validate_dual_workbook_session(session)
        metadata = collect_workbook_metadata(session)
        LOGGER.info("Workbook открыт: листов=%s", metadata.sheet_count)
        yield session
