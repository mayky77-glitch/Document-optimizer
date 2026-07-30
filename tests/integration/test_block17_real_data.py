"""Read-only invariance check using explicitly supplied real workbooks."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from report_processor.processing import ProcessingEngine, ProcessReportRequest, StageOutcome

from fixtures.processing.builders import fingerprint


class ReadOnlyAdapters:
    def inspect(self, context):
        return StageOutcome()

    def calculate(self, context):
        return StageOutcome()

    def audit(self, context):
        return StageOutcome(decision="allow_write")

    def write(self, context):
        return StageOutcome()


def _inputs() -> tuple[Path, Path]:
    source = os.getenv("DOCUMENT_OPTIMIZER_REAL_SOURCE_XLSX")
    target = os.getenv("DOCUMENT_OPTIMIZER_REAL_TARGET_XLSX")
    if not source or not target:
        pytest.skip("real XLSX paths are not set")
    return Path(source), Path(target)


@pytest.mark.slow
def test_real_source_and_target_remain_byte_for_byte_unchanged() -> None:
    source, target = _inputs()
    before = fingerprint(source), fingerprint(target)
    result = ProcessingEngine(ReadOnlyAdapters()).process_report(
        ProcessReportRequest(source, target)
    )
    assert result.exit_code == 0
    assert (fingerprint(source), fingerprint(target)) == before
