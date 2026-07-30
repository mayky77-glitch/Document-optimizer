from __future__ import annotations

import logging
from dataclasses import replace

from report_processor.domain.models import FileManifest
from report_processor.domain.statuses import SourceSelectionStatus
from report_processor.identifiers.document_index import document_indexes_equal
from report_processor.selection.explanation import build_selection_explanation
from report_processor.selection.filters import filter_source_candidates
from report_processor.selection.models import (
    SourceScoringConfig,
    SourceSelectionRequest,
    SourceSelectionResult,
)
from report_processor.selection.ranking import (
    rank_source_candidates,
    top_candidates_are_ambiguous,
)
from report_processor.selection.scoring import score_source_candidates

LOGGER = logging.getLogger(__name__)


def select_source_file(
    manifest: FileManifest,
    request: SourceSelectionRequest,
    *,
    scoring_config: SourceScoringConfig | None = None,
) -> SourceSelectionResult:
    LOGGER.info(
        "Начало выбора источника: индекс=%s, период=%s",
        request.target_index.normalized,
        request.target_period.normalized if request.target_period else None,
    )
    if not request.allowed_document_types:
        return _finalize(
            SourceSelectionResult(
                selected=None,
                candidates=(),
                rejected=(),
                status=SourceSelectionStatus.NO_ALLOWED_DOCUMENT_TYPES,
                warnings=(),
                explanation=(),
            )
        )

    filtered = filter_source_candidates(manifest.entries, request)
    LOGGER.info(
        "Просмотрено записей: %d; прошло фильтр: %d",
        filtered.inspected_count,
        len(filtered.accepted),
    )
    if not filtered.accepted:
        status = _empty_result_status(manifest, request, filtered.rejected)
        return _finalize(
            SourceSelectionResult(
                selected=None,
                candidates=(),
                rejected=filtered.rejected,
                status=status,
                warnings=(),
                explanation=(),
            )
        )

    config = scoring_config or SourceScoringConfig()
    scored = score_source_candidates(filtered.accepted, request, config)
    ranked = rank_source_candidates(scored)
    LOGGER.debug(
        "Ранжирование: %s",
        [(candidate.file_id, candidate.score) for candidate in ranked],
    )

    if _only_low_confidence_candidates(ranked):
        result = SourceSelectionResult(
            selected=None,
            candidates=ranked,
            rejected=filtered.rejected,
            status=SourceSelectionStatus.ONLY_LOW_CONFIDENCE_CANDIDATES,
            warnings=("LOW_CONFIDENCE_PERIOD",),
            explanation=(),
        )
    elif top_candidates_are_ambiguous(ranked):
        result = SourceSelectionResult(
            selected=None,
            candidates=ranked,
            rejected=filtered.rejected,
            status=SourceSelectionStatus.MULTIPLE_TOP_CANDIDATES,
            warnings=("MANUAL_SELECTION_REQUIRED",),
            explanation=(),
        )
    else:
        result = SourceSelectionResult(
            selected=ranked[0],
            candidates=ranked,
            rejected=filtered.rejected,
            status=SourceSelectionStatus.OK,
            warnings=ranked[0].warnings,
            explanation=(),
        )
    return _finalize(result)


def _empty_result_status(
    manifest: FileManifest,
    request: SourceSelectionRequest,
    rejected: tuple,
) -> str:
    if not manifest.entries:
        return SourceSelectionStatus.SOURCE_NOT_FOUND
    if not any(
        entry.document_index is not None
        and document_indexes_equal(entry.document_index, request.target_index)
        for entry in manifest.entries
    ):
        return SourceSelectionStatus.INDEX_NOT_AVAILABLE
    if request.target_period is not None and request.require_exact_period:
        matching_index_entries = [
            entry
            for entry in manifest.entries
            if entry.document_index is not None
            and document_indexes_equal(entry.document_index, request.target_index)
        ]
        has_exact_period = any(
            entry.document_period == request.target_period for entry in matching_index_entries
        )
        if not has_exact_period:
            return SourceSelectionStatus.PERIOD_NOT_AVAILABLE
    if rejected:
        return SourceSelectionStatus.ALL_CANDIDATES_REJECTED
    return SourceSelectionStatus.SOURCE_NOT_FOUND


def _only_low_confidence_candidates(candidates: tuple) -> bool:
    confidences = [
        candidate.entry.document_period_confidence
        for candidate in candidates
        if candidate.entry.document_period is not None
    ]
    return bool(confidences) and all(
        confidence is not None and confidence < 0.75 for confidence in confidences
    )


def _finalize(result: SourceSelectionResult) -> SourceSelectionResult:
    finalized = replace(result, explanation=build_selection_explanation(result))
    LOGGER.info("Статус выбора: %s", finalized.status)
    if finalized.selected is not None:
        LOGGER.info("Выбран относительный путь: %s", finalized.selected.entry.relative_path)
    return finalized
