"""Frozen public shapes and request validation for ProcessingContract-17.0."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest

from report_processor.processing import (
    PROCESSING_CONTRACT_VERSION,
    PROCESSING_ENGINE_VERSION,
    PROCESSING_STATE_VERSION,
    ProcessingExitCode,
    ProcessingResult,
    ProcessingState,
    ProcessMode,
    ProcessReportRequest,
)


def test_versions_modes_states_and_exit_groups_are_frozen(tmp_path) -> None:
    assert (
        PROCESSING_CONTRACT_VERSION,
        PROCESSING_ENGINE_VERSION,
        PROCESSING_STATE_VERSION,
    ) == ("ProcessingContract-17.0", "ProcessingEngine-17.0", "ProcessingState-17.0")
    assert tuple(ProcessMode) == ("inspect", "dry-run", "write")
    assert tuple(ProcessingState) == (
        "PENDING",
        "RUNNING",
        "SUCCEEDED",
        "SUCCEEDED_WITH_WARNINGS",
        "MANUAL_REVIEW_REQUIRED",
        "QUALITY_BLOCKED",
        "FAILED",
    )
    assert tuple(ProcessingExitCode) == (0, 1, 2, 3, 4, 5, 6)
    assert ProcessReportRequest(tmp_path / "source.xlsx", tmp_path / "target.xlsx")


def test_request_and_result_are_immutable_and_normalize_deterministic_values(tmp_path) -> None:
    request = ProcessReportRequest(
        str(tmp_path / "source.xlsx"),
        str(tmp_path / "target.xlsx"),
        options={"z": 1, "a": 2},
    )
    result = ProcessingResult(
        request=request,
        state=ProcessingState.SUCCEEDED_WITH_WARNINGS,
        exit_code=ProcessingExitCode.SUCCESS_WITH_WARNINGS,
        run_key="run",
        warnings=("Z", "A", "Z"),
        artifacts={"z": 1, "a": 2},
    )
    assert tuple(field.name for field in fields(ProcessReportRequest)) == (
        "source_path",
        "target_path",
        "mode",
        "strict",
        "output_path",
        "stage",
        "month",
        "rules_path",
        "audit_directory",
        "options",
        "cache_directory",
        "resume",
    )
    assert result.warnings == ("A", "Z")
    assert tuple(result.artifacts) == ("a", "z")
    with pytest.raises((AttributeError, FrozenInstanceError)):
        request.strict = False
    with pytest.raises(TypeError):
        request.options["new"] = "value"


@pytest.mark.parametrize("mode", (ProcessMode.INSPECT, ProcessMode.DRY_RUN))
def test_non_writing_modes_reject_an_output_path(tmp_path, mode: ProcessMode) -> None:
    with pytest.raises(ValueError, match="output_path"):
        ProcessReportRequest(
            tmp_path / "source.xlsx",
            tmp_path / "target.xlsx",
            mode,
            output_path=tmp_path / "out.xlsx",
        )


def test_write_mode_requires_an_output_path(tmp_path) -> None:
    with pytest.raises(ValueError, match="output_path"):
        ProcessReportRequest(tmp_path / "source.xlsx", tmp_path / "target.xlsx", ProcessMode.WRITE)
