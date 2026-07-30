"""Public API lock for the Block 17 processing boundary."""

from __future__ import annotations

from report_processor.processing import (
    PROCESSING_CONTRACT_VERSION,
    PROCESSING_ENGINE_VERSION,
    PROCESSING_STATE_VERSION,
    ProcessingEngine,
    process_report,
    process_reports,
)


def test_public_versions_and_entry_points_are_exported() -> None:
    assert (
        PROCESSING_CONTRACT_VERSION,
        PROCESSING_ENGINE_VERSION,
        PROCESSING_STATE_VERSION,
    ) == ("ProcessingContract-17.0", "ProcessingEngine-17.0", "ProcessingState-17.0")
    assert callable(ProcessingEngine)
    assert callable(process_report)
    assert callable(process_reports)
