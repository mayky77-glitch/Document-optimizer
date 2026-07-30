"""Public contracts for the Block 17 processing controller."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from pathlib import Path
from types import MappingProxyType

PROCESSING_CONTRACT_VERSION = "ProcessingContract-17.0"
PROCESSING_ENGINE_VERSION = "ProcessingEngine-17.0"
PROCESSING_STATE_VERSION = "ProcessingState-17.0"


class ProcessMode(StrEnum):
    INSPECT = "inspect"
    DRY_RUN = "dry-run"
    WRITE = "write"


class ProcessingState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    SUCCEEDED_WITH_WARNINGS = "SUCCEEDED_WITH_WARNINGS"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    QUALITY_BLOCKED = "QUALITY_BLOCKED"
    FAILED = "FAILED"


class ProcessingExitCode(IntEnum):
    SUCCESS = 0
    SUCCESS_WITH_WARNINGS = 1
    INVALID_INPUT = 2
    MANUAL_REVIEW_REQUIRED = 3
    QUALITY_BLOCKED = 4
    WRITE_OR_VERIFICATION_FAILED = 5
    CONTROLLED_INTERNAL_ERROR = 6


@dataclass(frozen=True, slots=True)
class FileSnapshot:
    path: Path
    sha256: str
    size: int
    mtime_ns: int


@dataclass(frozen=True, slots=True)
class ProcessReportRequest:
    """Input to the controller; business-specific inputs belong in ``options``."""

    source_path: Path
    target_path: Path
    mode: ProcessMode = ProcessMode.INSPECT
    strict: bool = True
    output_path: Path | None = None
    stage: str | None = None
    month: str | None = None
    rules_path: Path | None = None
    audit_directory: Path | None = None
    options: Mapping[str, object] = field(default_factory=dict)
    cache_directory: Path | None = None
    resume: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_path", Path(self.source_path))
        object.__setattr__(self, "target_path", Path(self.target_path))
        if self.output_path is not None:
            object.__setattr__(self, "output_path", Path(self.output_path))
        if self.rules_path is not None:
            object.__setattr__(self, "rules_path", Path(self.rules_path))
        if self.audit_directory is not None:
            object.__setattr__(self, "audit_directory", Path(self.audit_directory))
        if not isinstance(self.mode, ProcessMode):
            object.__setattr__(self, "mode", ProcessMode(self.mode))
        if self.mode is ProcessMode.WRITE and self.output_path is None:
            raise ValueError("output_path обязателен в режиме write")
        if self.mode is not ProcessMode.WRITE and self.output_path is not None:
            raise ValueError("output_path разрешён только в режиме write")
        object.__setattr__(self, "options", MappingProxyType(dict(sorted(self.options.items()))))


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    request: ProcessReportRequest
    state: ProcessingState
    exit_code: ProcessingExitCode
    run_key: str
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    input_snapshots: tuple[FileSnapshot, ...] = ()
    artifacts: Mapping[str, object] = field(default_factory=dict)
    resumed: bool = False
    contract_version: str = field(default=PROCESSING_CONTRACT_VERSION, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "warnings", tuple(sorted(set(self.warnings))))
        object.__setattr__(self, "errors", tuple(sorted(set(self.errors))))
        object.__setattr__(
            self, "artifacts", MappingProxyType(dict(sorted(self.artifacts.items())))
        )
