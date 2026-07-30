"""Public value models for AnalyticalStore-11.0."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

ANALYTICAL_CONTRACT_VERSION = "AnalyticalStore-11.0"
ANALYTICAL_SCHEMA_VERSION = "AnalyticalSchema-1"
MAX_QUERY_LIMIT = 10_000


@dataclass(frozen=True, slots=True)
class AnalyticalLoadResult:
    database_path: Path
    entity: str
    received_count: int
    inserted_count: int
    unchanged_count: int

    @property
    def row_count(self) -> int:
        return self.received_count


@dataclass(frozen=True, slots=True)
class AnalyticalQuery:
    """A fixed named view plus equality filters and a bounded result size."""

    name: str = "source_rows"
    filters: Mapping[str, str] | None = None
    limit: int = 1_000

    def __post_init__(self) -> None:
        copied = {} if self.filters is None else dict(self.filters)
        if any(
            not isinstance(key, str) or not isinstance(value, str) for key, value in copied.items()
        ):
            raise TypeError("filters должен быть отображением строк в строки")
        object.__setattr__(self, "filters", MappingProxyType(dict(sorted(copied.items()))))


@dataclass(frozen=True, slots=True)
class AnalyticalQueryResult:
    query_name: str
    columns: tuple[str, ...]
    rows: tuple[Mapping[str, Any], ...]

    @property
    def row_count(self) -> int:
        return len(self.rows)


@dataclass(frozen=True, slots=True)
class AnalyticalExportResult:
    output_path: Path
    row_count: int
    bytes_written: int
    contract_version: str = field(default=ANALYTICAL_CONTRACT_VERSION, init=False)
