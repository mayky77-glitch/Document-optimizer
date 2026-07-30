from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class StorageQuery:
    """Bounded, equality-only filters for canonical source rows."""

    source_file_id: str | None = None
    document_index: str | None = None
    document_period: str | None = None
    source_type: str | None = None
    limit: int | None = 1_000


@dataclass(frozen=True, slots=True)
class StorageWriteResult:
    database_path: Path
    received_count: int
    inserted_count: int
    updated_count: int
    unchanged_count: int

    @property
    def row_count(self) -> int:
        return self.received_count


@dataclass(frozen=True, slots=True)
class StorageExportResult:
    output_path: Path
    meta_path: Path
    row_count: int
    bytes_written: int
