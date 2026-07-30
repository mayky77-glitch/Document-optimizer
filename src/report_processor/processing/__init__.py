"""Block 17 public processing API."""

from .adapters import DefaultProcessingAdapters, ProcessingAdapters, ProcessingContext, StageOutcome
from .contracts import (
    PROCESSING_CONTRACT_VERSION,
    PROCESSING_ENGINE_VERSION,
    PROCESSING_STATE_VERSION,
    FileSnapshot,
    ProcessingExitCode,
    ProcessingResult,
    ProcessingState,
    ProcessMode,
    ProcessReportRequest,
)
from .engine import ProcessingEngine, highest_exit_code, process_report, process_reports

__all__ = [
    "PROCESSING_CONTRACT_VERSION",
    "PROCESSING_ENGINE_VERSION",
    "PROCESSING_STATE_VERSION",
    "DefaultProcessingAdapters",
    "FileSnapshot",
    "ProcessMode",
    "ProcessReportRequest",
    "ProcessingAdapters",
    "ProcessingContext",
    "ProcessingEngine",
    "ProcessingExitCode",
    "ProcessingResult",
    "ProcessingState",
    "StageOutcome",
    "highest_exit_code",
    "process_report",
    "process_reports",
]
