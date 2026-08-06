"""Stable lifecycle hooks for drawing-card workflow execution.

The workflow itself remains synchronous and deterministic.  This module merely
offers a small, serialisable progress contract that a job runner can persist or
publish while it executes the workflow elsewhere.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class DrawingCardLifecyclePhase(StrEnum):
    """Ordered, externally visible phases of one drawing-card attempt."""

    UPLOAD = "upload"
    SCHEMA_DETECTION = "schema_detection"
    EXTRACTION = "extraction"
    HIERARCHY_FILTERING = "hierarchy_filtering"
    MATCHING = "matching"
    REVIEW_PREPARATION = "review_preparation"
    OUTPUT_WRITING = "output_writing"
    VALIDATION = "validation"
    READY = "ready"


def utc_timestamp() -> str:
    """Return an unambiguous UTC timestamp suitable for a persisted manifest."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class DrawingCardProgress:
    """Bounded progress snapshot for one workflow attempt.

    ``total_*`` remains ``None`` while the workflow cannot know a safe total.
    A consumer must therefore not invent a percentage from unknown rows.
    """

    phase: DrawingCardLifecyclePhase
    processed_files: int = 0
    total_files: int | None = None
    processed_rows: int = 0
    total_rows: int | None = None
    started_at: str = ""
    updated_at: str = ""
    terminal_cause: str | None = None

    def __post_init__(self) -> None:
        for value in (self.processed_files, self.processed_rows):
            if value < 0:
                raise ValueError("processed progress counters must not be negative")
        for processed, total, label in (
            (self.processed_files, self.total_files, "files"),
            (self.processed_rows, self.total_rows, "rows"),
        ):
            if total is not None and (total < 0 or processed > total):
                raise ValueError(f"{label} progress counters must be bounded")


class DrawingCardWorkflowCancelled(RuntimeError):
    """Cooperative cancellation before a result workbook can be published."""

    terminal_cause = "cancelled"


ProgressCallback = Callable[[DrawingCardProgress], None]
CancellationProbe = Callable[[], bool]


class DrawingCardLifecycle:
    """Own timestamps and emit immutable snapshots for an attempt."""

    def __init__(self, callback: ProgressCallback | None = None) -> None:
        self._callback = callback
        self._started_at = utc_timestamp()
        self._last: DrawingCardProgress | None = None

    @property
    def last(self) -> DrawingCardProgress | None:
        return self._last

    def emit(
        self,
        phase: DrawingCardLifecyclePhase,
        *,
        processed_files: int = 0,
        total_files: int | None = None,
        processed_rows: int = 0,
        total_rows: int | None = None,
        terminal_cause: str | None = None,
    ) -> DrawingCardProgress:
        progress = DrawingCardProgress(
            phase=phase,
            processed_files=processed_files,
            total_files=total_files,
            processed_rows=processed_rows,
            total_rows=total_rows,
            started_at=self._started_at,
            updated_at=utc_timestamp(),
            terminal_cause=terminal_cause,
        )
        self._last = progress
        if self._callback is not None:
            self._callback(progress)
        return progress
