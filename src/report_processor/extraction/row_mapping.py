from __future__ import annotations

from dataclasses import replace

from report_processor.adapters import SourceAdapter
from report_processor.excel import DualWorkbookSession
from report_processor.schema import WorksheetSchema

from .models import CanonicalSourceRow
from .provenance import make_row_location
from .row_iterator import RowCandidate
from .row_validation import validate_canonical_source_row
from .statuses import CanonicalRowStatus, IssueSeverity


def map_row_candidate(
    session: DualWorkbookSession,
    schema: WorksheetSchema,
    adapter: SourceAdapter,
    candidate: RowCandidate,
    *,
    document_index: str | None,
    document_period: str | None,
) -> CanonicalSourceRow:
    location = make_row_location(
        session,
        sheet_name=schema.sheet_name,
        sheet_type=schema.sheet_type,
        row_number=candidate.row_number,
    )
    raw_row = adapter.build_raw_row(candidate.values, source_location=location)
    row = adapter.map_to_canonical(
        raw_row,
        document_index=document_index,
        document_period=document_period,
    )
    if candidate.is_empty:
        row = replace(
            row,
            status=CanonicalRowStatus.EMPTY.value,
            warnings=tuple(dict.fromkeys((*row.warnings, "EMPTY_ROW_INCLUDED"))),
        )

    issues = validate_canonical_source_row(row)
    issue_warnings = tuple(f"{issue.code}:{issue.message}" for issue in issues)
    if issue_warnings:
        row = replace(
            row,
            warnings=tuple(dict.fromkeys((*row.warnings, *issue_warnings))),
        )
    if any(issue.severity == IssueSeverity.ERROR.value for issue in issues):
        row = replace(row, status=CanonicalRowStatus.ERROR.value)
    elif issues and row.status == CanonicalRowStatus.OK.value:
        row = replace(row, status=CanonicalRowStatus.PARTIAL.value)
    return row
