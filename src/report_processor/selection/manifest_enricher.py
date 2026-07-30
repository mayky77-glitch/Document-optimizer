from __future__ import annotations

from dataclasses import replace
from pathlib import PurePosixPath

from report_processor.domain.models import FileManifest
from report_processor.inventory.file_manifest import build_manifest_summary
from report_processor.metadata.filename_status import extract_filename_status
from report_processor.metadata.periods import (
    extract_period_from_filename,
    extract_period_from_path,
)


def enrich_manifest_with_document_metadata(
    manifest: FileManifest,
    *,
    use_parent_paths: bool = True,
) -> FileManifest:
    enriched_entries = []
    for entry in manifest.entries:
        if use_parent_paths:
            relative = PurePosixPath(entry.relative_path.replace("\\", "/"))
            synthetic_path = str(relative.parent / entry.filename)
            period = extract_period_from_path(
                synthetic_path,
                include_parent_parts=True,
            )
        else:
            period = extract_period_from_filename(entry.filename)
        filename_status = extract_filename_status(entry.filename)
        revision = filename_status.revision_result
        enriched_entries.append(
            replace(
                entry,
                is_temporary=entry.is_temporary or filename_status.is_temporary,
                is_probable_copy=(entry.is_probable_copy or filename_status.is_probable_copy),
                is_probably_outdated=(
                    entry.is_probably_outdated or filename_status.is_probably_outdated
                ),
                document_period=period.value,
                document_period_status=str(period.status),
                document_period_confidence=period.confidence,
                document_period_candidates=list(period.candidates),
                document_period_warnings=[str(item) for item in period.warnings],
                document_revision=revision.value,
                document_revision_status=str(revision.status),
                document_revision_warnings=[str(item) for item in revision.warnings],
                is_final=filename_status.is_final,
                is_approved=filename_status.is_approved,
                is_draft=filename_status.is_draft,
            )
        )
    return replace(
        manifest,
        entries=enriched_entries,
        summary=build_manifest_summary(enriched_entries, manifest.source_kind),
        schema_version="3.0",
    )
