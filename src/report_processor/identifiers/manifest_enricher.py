"""Enrichment of existing file manifests with document indexes."""

from __future__ import annotations

import copy
import logging

from report_processor.domain.models import FileManifest
from report_processor.domain.statuses import IndexStatus, IndexWarning
from report_processor.identifiers.document_index import (
    extract_index_from_filename,
    extract_index_from_path,
)
from report_processor.inventory.file_manifest import build_manifest_summary

LOGGER = logging.getLogger(__name__)


def enrich_manifest_with_document_indexes(
    manifest: FileManifest,
    *,
    use_parent_paths: bool = True,
    allow_loose: bool = False,
) -> FileManifest:
    """Return a deep-copied manifest enriched from relative paths only."""

    enriched = copy.deepcopy(manifest)
    LOGGER.info(
        "Начато извлечение индексов для %d записей",
        len(enriched.entries),
    )

    for entry in enriched.entries:
        if entry.is_temporary:
            entry.document_index = None
            entry.document_index_status = IndexStatus.INDEX_NOT_PROCESSED.value
            entry.document_index_confidence = None
            entry.document_index_candidates = []
            entry.document_index_warnings = [IndexWarning.TEMPORARY_FILE_SKIPPED.value]
            LOGGER.debug("Временная запись пропущена: %s", entry.filename)
            continue

        if use_parent_paths:
            result = extract_index_from_path(
                entry.relative_path,
                include_parent_parts=True,
                allow_loose=allow_loose,
            )
        else:
            result = extract_index_from_filename(entry.filename, allow_loose=allow_loose)

        entry.document_index = result.value
        entry.document_index_status = result.status
        entry.document_index_candidates = [
            candidate.document_index for candidate in result.candidates
        ]
        entry.document_index_confidence = (
            max((candidate.confidence for candidate in result.candidates), default=None)
        )
        entry.document_index_warnings = list(result.warnings)
        LOGGER.debug("Индекс для %s: %s", entry.filename, result.status)

    enriched.summary = build_manifest_summary(enriched.entries, enriched.source_kind)
    LOGGER.info(
        "Обработано: %d; найдено: %d; "
        "неоднозначно: %d; низкая уверенность: %d",
        enriched.summary.total_entries,
        enriched.summary.entries_with_document_index,
        enriched.summary.entries_with_ambiguous_index,
        enriched.summary.entries_with_low_confidence_index,
    )
    return enriched
