from __future__ import annotations

from pathlib import Path

from report_processor.domain.models import FileManifestEntry


def regular_entry_path(entry: FileManifestEntry) -> Path:
    source_root = Path(entry.source_root)
    relative = Path(entry.relative_path)
    if source_root.is_file() or source_root.name == entry.filename:
        return source_root
    if relative.is_absolute():
        return relative
    return source_root / relative


def archive_entry_path(entry: FileManifestEntry) -> Path:
    if entry.archive_path:
        return Path(entry.archive_path)
    source_root = Path(entry.source_root)
    if source_root.suffix.lower() == ".zip":
        return source_root
    raise ValueError("В записи манифеста отсутствует archive_path")
