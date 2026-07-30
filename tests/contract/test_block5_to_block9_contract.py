"""Frozen read-only target-report public contract (Block 9)."""

from __future__ import annotations

from dataclasses import is_dataclass

from report_processor.target_report import (
    TargetReportReadRequest,
    TargetReportResult,
    TargetReportRow,
    TargetReportSchema,
    read_target_report,
)


def test_block9_public_api_and_immutable_versions_are_available() -> None:
    assert callable(read_target_report)
    assert is_dataclass(TargetReportReadRequest)
    assert is_dataclass(TargetReportResult)
    assert is_dataclass(TargetReportRow)
    assert is_dataclass(TargetReportSchema)
    assert TargetReportRow.__dataclass_params__.frozen
    assert TargetReportSchema.__dataclass_params__.frozen
