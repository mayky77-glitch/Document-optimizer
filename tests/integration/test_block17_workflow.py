"""Black-box mode, QC and controlled-failure behaviour for Block 17."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from openpyxl import Workbook

from report_processor.audit import AuditJournal, AuditStage, AuditState
from report_processor.processing import (
    DefaultProcessingAdapters,
    ProcessingContext,
    ProcessingEngine,
    ProcessingExitCode,
    ProcessingState,
    ProcessMode,
    ProcessReportRequest,
    StageOutcome,
)


class RecordingAdapters:
    def __init__(self, *, decision: str | None = None, warnings: tuple[str, ...] = ()) -> None:
        self.calls: list[str] = []
        self.decision = decision
        self.warnings = warnings
        self.temporary_directories: list[Path] = []

    def inspect(self, context):
        self.calls.append("inspect")
        self.temporary_directories.append(Path(context.temporary_directory))
        return StageOutcome(warnings=self.warnings)

    def calculate(self, context):
        self.calls.append("calculate")
        return StageOutcome()

    def audit(self, context):
        self.calls.append("audit")
        return StageOutcome(decision=self.decision)

    def write(self, context):
        self.calls.append("write")
        return StageOutcome(artifacts={"published": True})


@pytest.fixture
def inputs(tmp_path: Path) -> tuple[Path, Path]:
    source, target = tmp_path / "source.xlsx", tmp_path / "target.xlsx"
    source.write_bytes(b"source")
    target.write_bytes(b"target")
    return source, target


@pytest.mark.parametrize(
    ("mode", "expected_calls"),
    ((ProcessMode.INSPECT, ["inspect"]), (ProcessMode.DRY_RUN, ["inspect", "calculate", "audit"])),
)
def test_inspect_and_dry_run_never_publish_xlsx(inputs, tmp_path, mode, expected_calls) -> None:
    source, target = inputs
    adapters = RecordingAdapters(decision="allow_write")
    result = ProcessingEngine(adapters).process_report(ProcessReportRequest(source, target, mode))
    assert result.exit_code is ProcessingExitCode.SUCCESS
    assert adapters.calls == expected_calls
    assert not list(tmp_path.glob("*.xlsx"))[2:]
    assert all(not directory.exists() for directory in adapters.temporary_directories)


def test_write_uses_qc_gate_and_preserves_no_clobber(inputs, tmp_path) -> None:
    source, target = inputs
    existing = tmp_path / "existing.xlsx"
    existing.write_bytes(b"must remain")
    adapters = RecordingAdapters(decision="require_manual_review")
    result = ProcessingEngine(adapters).process_report(
        ProcessReportRequest(source, target, ProcessMode.WRITE, output_path=existing)
    )
    assert result.state is ProcessingState.MANUAL_REVIEW_REQUIRED
    assert result.exit_code is ProcessingExitCode.MANUAL_REVIEW_REQUIRED
    assert adapters.calls == ["inspect", "calculate", "audit"]
    assert existing.read_bytes() == b"must remain"


def test_strict_warning_blocks_but_non_strict_allow_warning_can_publish(inputs, tmp_path) -> None:
    source, target = inputs
    strict = RecordingAdapters(decision="allow_write_with_warnings", warnings=("WARN",))
    strict_result = ProcessingEngine(strict).process_report(
        ProcessReportRequest(
            source, target, ProcessMode.WRITE, output_path=tmp_path / "strict.xlsx"
        )
    )
    permissive = RecordingAdapters(decision="allow_write_with_warnings", warnings=("WARN",))
    permissive_result = ProcessingEngine(permissive).process_report(
        ProcessReportRequest(
            source,
            target,
            ProcessMode.WRITE,
            strict=False,
            output_path=tmp_path / "non-strict.xlsx",
        )
    )
    assert strict_result.exit_code is ProcessingExitCode.MANUAL_REVIEW_REQUIRED
    assert strict.calls == ["inspect", "calculate", "audit"]
    assert permissive_result.exit_code is ProcessingExitCode.SUCCESS_WITH_WARNINGS
    assert permissive.calls == ["inspect", "calculate", "audit", "write"]


def test_all_exit_groups_are_reachable_as_controlled_results(inputs, tmp_path) -> None:
    source, target = inputs
    success = ProcessingEngine(RecordingAdapters()).process_report(
        ProcessReportRequest(source, target)
    )
    warning = ProcessingEngine(RecordingAdapters(warnings=("WARN",))).process_report(
        ProcessReportRequest(source, target)
    )
    invalid = ProcessingEngine(RecordingAdapters()).process_report(
        ProcessReportRequest(tmp_path / "missing", target)
    )
    manual = ProcessingEngine(RecordingAdapters(decision="require_manual_review")).process_report(
        ProcessReportRequest(
            source, target, ProcessMode.WRITE, output_path=tmp_path / "manual.xlsx"
        )
    )
    blocked = ProcessingEngine(RecordingAdapters(decision="block_write")).process_report(
        ProcessReportRequest(
            source, target, ProcessMode.WRITE, output_path=tmp_path / "blocked.xlsx"
        )
    )
    assert [item.exit_code for item in (success, warning, invalid, manual, blocked)] == [
        ProcessingExitCode.SUCCESS,
        ProcessingExitCode.SUCCESS_WITH_WARNINGS,
        ProcessingExitCode.INVALID_INPUT,
        ProcessingExitCode.MANUAL_REVIEW_REQUIRED,
        ProcessingExitCode.QUALITY_BLOCKED,
    ]


def test_adapter_fault_is_contained_as_controlled_internal_error(inputs) -> None:
    source, target = inputs

    class BrokenAdapters(RecordingAdapters):
        def inspect(self, context):
            raise RuntimeError("adapter fault")

    result = ProcessingEngine(BrokenAdapters()).process_report(ProcessReportRequest(source, target))
    assert result.state is ProcessingState.FAILED
    assert result.exit_code is ProcessingExitCode.CONTROLLED_INTERNAL_ERROR
    assert result.errors


def test_default_dry_run_uses_public_upstream_stages_without_internal_error(
    monkeypatch, tmp_path
) -> None:
    source, target = tmp_path / "source.xlsx", tmp_path / "target.xlsx"
    for path in (source, target):
        workbook = Workbook()
        workbook.save(path)
        workbook.close()
    calls: list[str] = []
    stage_functions = (
        ("report_processor.schema", "analyze_workbook_schema", "schema"),
        ("report_processor.extraction", "extract_supported_workbook_rows", "extraction"),
        ("report_processor.training_data", "prepare_training_data", "training"),
        ("report_processor.normalization", "normalize_training_rows", "normalization"),
        ("report_processor.matching", "match_rows", "matching"),
        ("report_processor.calculation", "calculate_matches", "calculation"),
        ("report_processor.quality_control", "evaluate_quality_control", "quality"),
    )
    for module_path, attribute, stage in stage_functions:
        module = __import__(module_path, fromlist=[attribute])
        original = getattr(module, attribute)

        def traced(*args, _original=original, _stage=stage, **kwargs):
            calls.append(_stage)
            return _original(*args, **kwargs)

        monkeypatch.setattr(module, attribute, traced)
    result = ProcessingEngine().process_report(
        ProcessReportRequest(source, target, ProcessMode.DRY_RUN)
    )
    assert result.exit_code is not ProcessingExitCode.CONTROLLED_INTERNAL_ERROR
    assert set(calls) >= {
        "schema",
        "extraction",
        "training",
        "normalization",
        "matching",
        "calculation",
        "quality",
    }


def test_default_audit_and_write_record_persistent_block16_lifecycle(
    monkeypatch, inputs, tmp_path
) -> None:
    source, target = inputs
    audit_directory = tmp_path / "audit"
    request = ProcessReportRequest(
        source,
        target,
        ProcessMode.WRITE,
        output_path=tmp_path / "published.xlsx",
        audit_directory=audit_directory,
    )
    quality_report = SimpleNamespace(
        issues=(),
        decision=SimpleNamespace(value="allow_write"),
        input_digest="d" * 64,
        summary=SimpleNamespace(calculation_count=0),
        report_id="r" * 64,
    )
    monkeypatch.setattr(
        "report_processor.quality_control.evaluate_quality_control", lambda *args: quality_report
    )
    monkeypatch.setattr(
        "report_processor.excel_writer.write_target_report",
        lambda *args: SimpleNamespace(output_sha256="e" * 64, warnings=()),
    )
    recoveries: list[str] = []
    original_recover = AuditJournal.recover

    def traced_recover(self, run_id, *args, **kwargs):
        recoveries.append(run_id)
        return original_recover(self, run_id, *args, **kwargs)

    monkeypatch.setattr(AuditJournal, "recover", traced_recover)
    context = ProcessingContext(
        ProcessMode.WRITE,
        True,
        "run-key",
        tmp_path,
        {
            "request": request,
            "source_sha256": "a" * 64,
            "target_sha256": "b" * 64,
            "matches": (),
            "calculations": (),
            "rule_set": SimpleNamespace(content_hash="c" * 64),
            "target_report": SimpleNamespace(schema=SimpleNamespace()),
        },
    )
    adapters = DefaultProcessingAdapters()
    audited = adapters.audit(context)
    context.values.update(audited.artifacts)
    written = adapters.write(context)
    run_id = str(audited.artifacts["audit_run_id"])
    with AuditJournal(audit_directory / "journal.sqlite3") as journal:
        events = journal.validate_run(run_id)
    assert audited.artifacts["audit_boundary"] == AuditState.DATA_COMMITTED
    assert written.artifacts["audit_boundary"] == AuditState.EXPORT_VERIFIED
    assert [(event.controlled_stage_code, event.controlled_state_code) for event in events] == [
        (AuditStage.RUN, AuditState.PENDING),
        (AuditStage.DATA, AuditState.DATA_COMMITTED),
        (AuditStage.EXPORT, AuditState.EXPORT_PREPARED),
        (AuditStage.EXPORT, AuditState.EXPORT_VERIFIED),
    ]
    assert recoveries == [run_id]
    assert (audit_directory / f"{run_id}.json").is_file()
