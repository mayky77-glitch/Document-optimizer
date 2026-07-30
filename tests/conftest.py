from __future__ import annotations

from datetime import UTC, datetime

import pytest

from report_processor.domain.models import FileManifest, FileManifestEntry
from report_processor.inventory.file_classifier import classify_file_by_name
from report_processor.inventory.file_manifest import build_manifest_summary


@pytest.fixture
def make_entry():
    def factory(
        filename: str,
        *,
        file_id: str | None = None,
        relative_path: str | None = None,
        document_type: str | None = None,
        extension: str | None = None,
        is_archive_entry: bool = False,
        source_type: str | None = None,
        modified_at: datetime | None = None,
    ) -> FileManifestEntry:
        classification = classify_file_by_name(filename)
        return FileManifestEntry(
            file_id=file_id or filename,
            source_type=source_type or ("archive_entry" if is_archive_entry else "file"),
            source_root="/redacted-fixture/source",
            relative_path=relative_path or filename,
            filename=filename,
            extension=extension or ("." + filename.rsplit(".", 1)[-1].lower()),
            size_bytes=None,
            compressed_size_bytes=None,
            modified_at=modified_at or datetime(2026, 7, 1, tzinfo=UTC),
            crc32=None,
            is_archive_entry=is_archive_entry,
            archive_path="/redacted-fixture/archive.zip" if is_archive_entry else None,
            document_type=document_type or classification.document_type,
            document_markers=classification.document_markers,
            is_temporary=classification.is_temporary,
            is_probable_copy=classification.is_probable_copy,
            is_probably_outdated=classification.is_probably_outdated,
            status="OK",
        )

    return factory


@pytest.fixture
def make_manifest():
    def factory(entries: list[FileManifestEntry]) -> FileManifest:
        return FileManifest(
            source_path="/redacted-fixture/source",
            source_kind="directory",
            created_at=datetime(2026, 7, 1, tzinfo=UTC),
            entries=entries,
            summary=build_manifest_summary(entries, "directory"),
        )

    return factory
