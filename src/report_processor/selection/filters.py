from __future__ import annotations

from collections.abc import Iterable

from report_processor.domain.models import FileManifestEntry
from report_processor.identifiers.document_index import document_indexes_equal
from report_processor.selection.models import (
    CandidateFilterResult,
    SourceCandidate,
    SourceSelectionRequest,
)

SUPPORTED_EXCEL_EXTENSIONS = {".xlsx", ".xlsm", ".xls", ".xlsb", ".ods"}


def filter_source_candidates(
    entries: Iterable[FileManifestEntry],
    request: SourceSelectionRequest,
) -> CandidateFilterResult:
    accepted: list[SourceCandidate] = []
    rejected: list[SourceCandidate] = []
    inspected = 0
    allowed_types = set(request.allowed_document_types)

    for entry in entries:
        inspected += 1
        reasons = _rejection_reasons(entry, request, allowed_types)
        candidate = SourceCandidate(
            file_id=entry.file_id,
            entry=entry,
            score=0,
            rank=None,
            accepted=not reasons,
            rejection_reasons=tuple(reasons),
            score_components=(),
            warnings=(),
        )
        (rejected if reasons else accepted).append(candidate)

    return CandidateFilterResult(
        accepted=tuple(accepted),
        rejected=tuple(rejected),
        inspected_count=inspected,
    )


def _rejection_reasons(
    entry: FileManifestEntry,
    request: SourceSelectionRequest,
    allowed_types: set[str],
) -> list[str]:
    reasons: list[str] = []
    if _is_directory(entry):
        reasons.append("DIRECTORY_ENTRY")
    if entry.document_index is None:
        reasons.append("INDEX_NOT_AVAILABLE")
    elif not document_indexes_equal(entry.document_index, request.target_index):
        reasons.append("INDEX_MISMATCH")
    if entry.is_temporary:
        reasons.append("TEMPORARY_FILE")
    if entry.extension.lower() not in SUPPORTED_EXCEL_EXTENSIONS:
        reasons.append("UNSUPPORTED_EXTENSION")
    if entry.document_type.lower() not in allowed_types:
        reasons.append("DOCUMENT_TYPE_NOT_ALLOWED")
    if entry.is_probably_outdated and not entry.is_draft and not request.include_outdated:
        reasons.append("PROBABLY_OUTDATED")
    if entry.is_draft and not request.include_drafts:
        reasons.append("DRAFT_FILE")
    if entry.is_probable_copy and not request.include_probable_copies:
        reasons.append("PROBABLE_COPY")
    _append_period_rejection(reasons, entry, request)
    return reasons


def _append_period_rejection(
    reasons: list[str],
    entry: FileManifestEntry,
    request: SourceSelectionRequest,
) -> None:
    if request.target_period is None:
        return
    if entry.document_period is None:
        if not request.allow_unknown_period:
            reasons.append("UNKNOWN_PERIOD_NOT_ALLOWED")
        return
    if entry.document_period != request.target_period and request.require_exact_period:
        reasons.append("PERIOD_MISMATCH")


def _is_directory(entry: FileManifestEntry) -> bool:
    return entry.source_type.lower() in {"directory", "folder"}
