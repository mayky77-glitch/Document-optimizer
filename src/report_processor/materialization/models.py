from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from report_processor.selection.models import SourceCandidate


@dataclass(frozen=True, slots=True)
class MaterializationRequest:
    candidate: SourceCandidate
    workspace_root: Path | None = None
    max_file_size_bytes: int = 2 * 1024**3
    verify_zip_crc: bool = True


@dataclass(frozen=True, slots=True)
class MaterializedSource:
    local_path: Path
    original_file_id: str
    original_relative_path: str
    source_kind: str
    archive_path: str | None
    was_extracted: bool
    temporary: bool
    size_bytes: int
    extension: str
    cleanup_required: bool
    warnings: tuple[str, ...]
