"""CLI parsing and dispatch for the Block 17 process command."""

from __future__ import annotations

import argparse

from report_processor.cli_process import add_process_parser, run_process
from report_processor.processing import (
    ProcessingExitCode,
    ProcessingResult,
    ProcessingState,
    ProcessMode,
    ProcessReportRequest,
)


def test_process_parser_exposes_only_frozen_modes_and_strictness() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_process_parser(subparsers)
    args = parser.parse_args(
        [
            "process",
            "--source",
            "source.xlsx",
            "--target",
            "target.xlsx",
            "--mode",
            "dry-run",
            "--non-strict",
            "--rules",
            "rules.yaml",
            "--audit-directory",
            "audit",
        ]
    )
    assert (args.command, args.mode, args.non_strict, args.output) == (
        "process",
        "dry-run",
        True,
        None,
    )
    assert (args.rules, args.audit_directory) == ("rules.yaml", "audit")


def test_dispatch_maps_arguments_to_request_and_returns_contract_exit_code(
    monkeypatch, tmp_path
) -> None:
    captured: list[ProcessReportRequest] = []

    def fake_process(request: ProcessReportRequest) -> ProcessingResult:
        captured.append(request)
        return ProcessingResult(
            request, ProcessingState.QUALITY_BLOCKED, ProcessingExitCode.QUALITY_BLOCKED, "run"
        )

    monkeypatch.setattr("report_processor.cli_process.process_report", fake_process)
    args = argparse.Namespace(
        source=tmp_path / "source.xlsx",
        target=tmp_path / "target.xlsx",
        mode="write",
        non_strict=True,
        output=tmp_path / "out.xlsx",
        stage="stage",
        month="2026-07",
        rules=tmp_path / "rules.yaml",
        audit_directory=tmp_path / "audit",
        cache_directory=tmp_path / "cache",
        resume=True,
    )
    assert run_process(args) == 4
    assert captured == [
        ProcessReportRequest(
            args.source,
            args.target,
            ProcessMode.WRITE,
            strict=False,
            output_path=args.output,
            stage="stage",
            month="2026-07",
            rules_path=args.rules,
            audit_directory=args.audit_directory,
            cache_directory=args.cache_directory,
            resume=True,
        )
    ]
