"""Оркестрация построения файлового манифеста и его сводки."""

import logging
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from report_processor.domain.exceptions import SourceAccessError, SourceNotFoundError
from report_processor.domain.models import FileManifest, FileManifestEntry, ManifestSummary
from report_processor.domain.statuses import IndexStatus, StatusCode
from report_processor.inventory.archive_scanner import scan_zip_archive
from report_processor.inventory.scanner import create_file_entry
from report_processor.inventory.scanner import scan_directory as scan_directory_entries

LOGGER = logging.getLogger(__name__)


def _sorted_counter(values: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def build_manifest_summary(
    entries: list[FileManifestEntry], source_kind: str
) -> ManifestSummary:
    """Построить детерминированную агрегированную сводку по записям."""

    total_uncompressed = sum(entry.size_bytes or 0 for entry in entries)
    total_compressed = sum(entry.compressed_size_bytes or 0 for entry in entries)
    compression_ratio: float | None = None
    if source_kind == "zip" and total_compressed > 0:
        compression_ratio = total_uncompressed / total_compressed

    return ManifestSummary(
        total_entries=len(entries),
        total_size_bytes=total_uncompressed,
        files_by_extension=_sorted_counter(
            [entry.extension if entry.extension else "<none>" for entry in entries]
        ),
        files_by_document_type=_sorted_counter([entry.document_type for entry in entries]),
        files_by_document_marker=_sorted_counter(
            [marker for entry in entries for marker in entry.document_markers]
        ),
        temporary_files=sum(entry.is_temporary for entry in entries),
        probable_copies=sum(entry.is_probable_copy for entry in entries),
        probably_outdated_files=sum(entry.is_probably_outdated for entry in entries),
        unsafe_archive_entries=sum(
            StatusCode.UNSAFE_ARCHIVE_PATH.value in entry.warnings for entry in entries
        ),
        warnings_count=sum(len(entry.warnings) for entry in entries),
        unreadable_files=sum(entry.status == StatusCode.UNREADABLE_FILE.value for entry in entries),
        total_compressed_size=total_compressed if source_kind == "zip" else None,
        total_uncompressed_size=total_uncompressed if source_kind == "zip" else None,
        compression_ratio=compression_ratio,
        entries_with_document_index=sum(
            entry.document_index is not None
            and entry.document_index_status == IndexStatus.OK.value
            for entry in entries
        ),
        entries_without_document_index=sum(
            entry.document_index_status == IndexStatus.INDEX_NOT_FOUND.value for entry in entries
        ),
        entries_with_ambiguous_index=sum(
            entry.document_index_status == IndexStatus.MULTIPLE_INDEX_CANDIDATES.value
            for entry in entries
        ),
        entries_with_low_confidence_index=sum(
            entry.document_index_status == IndexStatus.LOW_CONFIDENCE_INDEX.value
            for entry in entries
        ),
        unique_document_indexes=len(
            {
                entry.document_index.normalized
                for entry in entries
                if entry.document_index is not None
                and entry.document_index_status == IndexStatus.OK.value
            }
        ),
        files_by_document_index=_sorted_counter(
            [
                entry.document_index.normalized
                for entry in entries
                if entry.document_index is not None
                and entry.document_index_status == IndexStatus.OK.value
            ]
        ),
    )


def build_file_manifest(source_path: Path, recursive: bool = True) -> FileManifest:
    """Построить манифест для каталога, одного файла или ZIP-архива."""

    source_path = source_path.expanduser()
    LOGGER.info("Начало инвентаризации источника: %s", source_path)

    if not source_path.exists():
        raise SourceNotFoundError(source_path)
    if source_path.is_symlink():
        raise SourceAccessError(source_path, "символические ссылки не поддерживаются как источник")

    if source_path.is_dir():
        source_kind = "directory"
        entries = scan_directory_entries(source_path, recursive=recursive)
    elif source_path.is_file() and source_path.suffix.casefold() == ".zip":
        source_kind = "zip"
        entries = scan_zip_archive(source_path)
    elif source_path.is_file():
        source_kind = "file"
        entries = [create_file_entry(source_path, source_path.parent, Path(source_path.name))]
    else:
        raise SourceAccessError(source_path, "неподдерживаемый тип файловой системы")

    manifest = FileManifest(
        source_path=str(source_path.resolve(strict=False)),
        source_kind=source_kind,
        created_at=datetime.now(tz=UTC),
        entries=entries,
        summary=build_manifest_summary(entries, source_kind),
    )
    LOGGER.info(
        "Инвентаризация завершена: тип=%s, записей=%d, предупреждений=%d",
        source_kind,
        manifest.summary.total_entries,
        manifest.summary.warnings_count,
    )
    return manifest
