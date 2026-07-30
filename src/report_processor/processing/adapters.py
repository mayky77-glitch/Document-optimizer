"""Narrow adapter boundary between Block 17 and the existing Blocks 1--16."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from .contracts import ProcessMode


@dataclass(frozen=True, slots=True)
class StageOutcome:
    """Data returned by one upstream stage without prescribing its domain model."""

    artifacts: Mapping[str, object] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    decision: str | None = None


class ProcessingAdapters(Protocol):
    """Adapters call established public APIs; the controller owns no stage logic."""

    def inspect(self, context: ProcessingContext) -> StageOutcome: ...

    def calculate(self, context: ProcessingContext) -> StageOutcome: ...

    def audit(self, context: ProcessingContext) -> StageOutcome: ...

    def write(self, context: ProcessingContext) -> StageOutcome: ...


@dataclass(slots=True)
class ProcessingContext:
    mode: ProcessMode
    strict: bool
    run_key: str
    temporary_directory: object
    values: dict[str, object] = field(default_factory=dict)


class DefaultProcessingAdapters:
    """Minimal concrete bridge to existing public APIs.

    Domain-specific selections and rules are deliberately passed by the caller's
    integration adapter; this class keeps the public default safe and read-only.
    """

    def inspect(self, context: ProcessingContext) -> StageOutcome:
        from report_processor.inventory import build_file_manifest

        request = context.values["request"]
        source = build_file_manifest(request.source_path)
        target = build_file_manifest(request.target_path)
        return StageOutcome(
            artifacts={"source_manifest": source, "target_manifest": target},
        )

    def calculate(self, context: ProcessingContext) -> StageOutcome:
        raise RuntimeError("Нужен integration ProcessingAdapters для Blocks 2--14")

    def audit(self, context: ProcessingContext) -> StageOutcome:
        raise RuntimeError("Нужен integration ProcessingAdapters для Block 16")

    def write(self, context: ProcessingContext) -> StageOutcome:
        raise RuntimeError("Нужен integration ProcessingAdapters для Block 15")
