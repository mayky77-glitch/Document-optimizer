"""Типизированные модели инвентаризации файлов."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from report_processor.domain.statuses import IndexStatus
from report_processor.identifiers.models import DocumentIndex

if TYPE_CHECKING:
    from report_processor.metadata.period_models import DocumentPeriod
    from report_processor.metadata.revisions import DocumentRevision

MANIFEST_SCHEMA_VERSION = "2.0"


@dataclass(slots=True, frozen=True)
class FileClassification:
    """Результат классификации имени файла без открытия его содержимого."""

    normalized_name: str
    document_type: str
    document_markers: list[str]
    is_temporary: bool
    is_probable_copy: bool
    is_probably_outdated: bool


@dataclass(slots=True)
class FileManifestEntry:
    """Одна запись файлового манифеста с файловым provenance."""

    file_id: str
    source_type: str
    source_root: str
    relative_path: str
    filename: str
    extension: str

    size_bytes: int | None
    compressed_size_bytes: int | None
    modified_at: datetime | None
    crc32: int | None

    is_archive_entry: bool
    archive_path: str | None

    document_type: str
    document_markers: list[str]

    is_temporary: bool
    is_probable_copy: bool
    is_probably_outdated: bool

    status: str
    warnings: list[str] = field(default_factory=list)
    document_index: DocumentIndex | None = None
    document_index_status: str = IndexStatus.INDEX_NOT_PROCESSED.value
    document_index_confidence: float | None = None
    document_index_candidates: list[DocumentIndex] = field(default_factory=list)
    document_index_warnings: list[str] = field(default_factory=list)
    document_period: DocumentPeriod | None = None
    document_period_status: str = "PERIOD_NOT_PROCESSED"
    document_period_confidence: float | None = None
    document_period_candidates: list[DocumentPeriod] = field(default_factory=list)
    document_period_warnings: list[str] = field(default_factory=list)
    document_revision: DocumentRevision | None = None
    document_revision_status: str = "REVISION_NOT_PROCESSED"
    document_revision_warnings: list[str] = field(default_factory=list)
    is_final: bool = False
    is_approved: bool = False
    is_draft: bool = False
    extra: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class ManifestSummary:
    """Агрегированная сводка по манифесту."""

    total_entries: int
    total_size_bytes: int
    files_by_extension: dict[str, int]
    files_by_document_type: dict[str, int]
    files_by_document_marker: dict[str, int]
    temporary_files: int
    probable_copies: int
    probably_outdated_files: int
    unsafe_archive_entries: int
    warnings_count: int
    unreadable_files: int = 0
    total_compressed_size: int | None = None
    total_uncompressed_size: int | None = None
    compression_ratio: float | None = None
    entries_with_document_index: int = 0
    entries_without_document_index: int = 0
    entries_with_ambiguous_index: int = 0
    entries_with_low_confidence_index: int = 0
    unique_document_indexes: int = 0
    files_by_document_index: dict[str, int] = field(default_factory=dict)
    entries_with_period: int = 0
    entries_without_period: int = 0
    entries_with_ambiguous_period: int = 0
    entries_with_revision: int = 0
    files_by_period: dict[str, int] = field(default_factory=dict)
    files_by_revision_status: dict[str, int] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class FileManifest:
    """Полный результат инвентаризации одного источника."""

    source_path: str
    source_kind: str
    created_at: datetime
    entries: list[FileManifestEntry]
    summary: ManifestSummary
    schema_version: str = MANIFEST_SCHEMA_VERSION
    extra: dict[str, Any] = field(default_factory=dict, repr=False)
