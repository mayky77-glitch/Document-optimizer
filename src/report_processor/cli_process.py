"""CLI parser/dispatch adapter; shared CLI wiring remains outside Block 17."""

from __future__ import annotations

import argparse
from pathlib import Path

from .processing import (
    ProcessingEngine,
    ProcessingExitCode,
    ProcessMode,
    ProcessReportRequest,
    process_report,
)


def add_process_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("process", help="Запустить единый processing pipeline")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument(
        "--mode", choices=tuple(mode.value for mode in ProcessMode), default="inspect"
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--stage")
    parser.add_argument("--month")
    parser.add_argument("--rules-path", type=Path)
    parser.add_argument("--audit-directory", type=Path)
    parser.add_argument("--non-strict", action="store_true")
    parser.add_argument("--cache-directory", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        default="INFO",
    )


def run_process(args: argparse.Namespace, adapters: object | None = None) -> int:
    try:
        request = ProcessReportRequest(
            source_path=args.source,
            target_path=args.target,
            mode=ProcessMode(args.mode),
            strict=not args.non_strict,
            output_path=args.output,
            stage=args.stage,
            month=args.month,
            rules_path=args.rules_path,
            audit_directory=args.audit_directory,
            cache_directory=args.cache_directory,
            resume=args.resume,
        )
    except ValueError:
        return int(ProcessingExitCode.INVALID_INPUT)
    result = (
        process_report(request)
        if adapters is None
        else ProcessingEngine(adapters).process_report(request)
    )
    return int(result.exit_code)
