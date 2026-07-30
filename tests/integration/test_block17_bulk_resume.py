"""Deterministic bulk, resume and input-integrity processing checks."""

from __future__ import annotations

from pathlib import Path

from report_processor.processing import (
    ProcessingEngine,
    ProcessingExitCode,
    ProcessMode,
    ProcessReportRequest,
    StageOutcome,
)


class CountingAdapters:
    def __init__(self) -> None:
        self.inspections = 0

    def inspect(self, context):
        self.inspections += 1
        return StageOutcome()

    def calculate(self, context):
        return StageOutcome()

    def audit(self, context):
        return StageOutcome(decision="allow_write")

    def write(self, context):
        return StageOutcome()


def _request(tmp_path: Path, name: str, **kwargs) -> ProcessReportRequest:
    source, target = tmp_path / f"{name}-source.xlsx", tmp_path / f"{name}-target.xlsx"
    source.write_bytes(f"source-{name}".encode())
    target.write_bytes(f"target-{name}".encode())
    return ProcessReportRequest(source, target, **kwargs)


def test_bulk_keeps_request_order_and_isolates_controlled_failure(tmp_path) -> None:
    adapters = CountingAdapters()
    first = _request(tmp_path, "first")
    invalid = ProcessReportRequest(tmp_path / "missing.xlsx", first.target_path)
    third = _request(tmp_path, "third")
    results = ProcessingEngine(adapters).process_reports((first, invalid, third))
    assert [result.request for result in results] == [first, invalid, third]
    assert [result.exit_code for result in results] == [
        ProcessingExitCode.SUCCESS,
        ProcessingExitCode.INVALID_INPUT,
        ProcessingExitCode.SUCCESS,
    ]
    assert adapters.inspections == 2


def test_repeat_is_deterministic_and_resume_rejects_changed_input_hashes(tmp_path) -> None:
    cache = tmp_path / "cache"
    adapters = CountingAdapters()
    request = _request(tmp_path, "repeat", cache_directory=cache)
    engine = ProcessingEngine(adapters)
    first = engine.process_report(request)
    repeated = engine.process_report(request)
    resumed = engine.process_report(
        ProcessReportRequest(
            request.source_path, request.target_path, cache_directory=cache, resume=True
        )
    )
    request.source_path.write_bytes(b"changed source")
    changed = engine.process_report(
        ProcessReportRequest(
            request.source_path, request.target_path, cache_directory=cache, resume=True
        )
    )
    assert (first.run_key, first.exit_code) == (repeated.run_key, repeated.exit_code)
    assert resumed.resumed is True
    assert changed.resumed is False
    assert changed.exit_code in {
        ProcessingExitCode.INVALID_INPUT,
        ProcessingExitCode.WRITE_OR_VERIFICATION_FAILED,
    }
    assert changed.run_key != first.run_key


def test_input_change_during_run_is_a_verification_failure(tmp_path) -> None:
    request = _request(tmp_path, "mutated")

    class MutatingAdapters(CountingAdapters):
        def inspect(self, context):
            request.source_path.write_bytes(b"changed during run")
            return StageOutcome()

    result = ProcessingEngine(MutatingAdapters()).process_report(request)
    assert result.exit_code is ProcessingExitCode.WRITE_OR_VERIFICATION_FAILED
    assert result.errors


def test_resume_cache_does_not_store_a_workbook_payload(tmp_path) -> None:
    cache = tmp_path / "cache"
    request = _request(tmp_path, "cache", cache_directory=cache, mode=ProcessMode.DRY_RUN)
    ProcessingEngine(CountingAdapters()).process_report(request)
    payloads = list(cache.glob("*.json"))
    assert len(payloads) == 1
    assert ".xlsx" not in payloads[0].read_text(encoding="utf-8")


def test_corrupt_partial_resume_cache_is_rejected_and_leaves_no_temporary_files(tmp_path) -> None:
    cache = tmp_path / "cache"
    request = _request(tmp_path, "corrupt", cache_directory=cache, resume=True)
    cache.mkdir()
    (cache / "partial.json").write_text("{broken", encoding="utf-8")
    result = ProcessingEngine(CountingAdapters()).process_report(request)
    assert result.exit_code in {
        ProcessingExitCode.INVALID_INPUT,
        ProcessingExitCode.WRITE_OR_VERIFICATION_FAILED,
    }
    assert not list(cache.glob("*.tmp"))
