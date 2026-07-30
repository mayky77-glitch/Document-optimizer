"""CLI adapter for bounded workbook schema detection."""

from __future__ import annotations

import argparse
import logging
from dataclasses import replace
from pathlib import Path

from report_processor.cli_inspect import resolve_workbook_candidate
from report_processor.domain.exceptions import ReportProcessorError
from report_processor.schema import analyze_workbook_schema, create_default_schema_config
from report_processor.schema.cli_exit_codes import DetectSchemaExitCode
from report_processor.schema.exceptions import SchemaDetectionError
from report_processor.schema.serialization import save_workbook_schema_json
from report_processor.workflow import prepared_workbook_session

LOGGER = logging.getLogger(__name__)


def add_detect_schema_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("detect-schema", help="Распознать структуру Excel-книги")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--file-id")
    parser.add_argument("--selection", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sheet")
    parser.add_argument("--max-scan-rows", type=int, default=60)
    parser.add_argument("--max-scan-columns", type=int, default=120)
    parser.add_argument("--min-confidence", type=float, default=0.70)
    parser.add_argument("--max-file-size-mb", type=int, default=2048)
    parser.add_argument(
        "--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"), default="INFO"
    )


def _exit_code(schema) -> int:
    statuses = {worksheet.status for worksheet in schema.worksheets}
    if any("AMBIGUOUS" in status for status in statuses):
        return int(DetectSchemaExitCode.AMBIGUOUS_STRUCTURE)
    if {"HEADER_NOT_FOUND", "UNKNOWN_SHEET_TYPE"} & statuses:
        return int(DetectSchemaExitCode.STRUCTURE_NOT_RECOGNIZED)
    if schema.status == "LOW_CONFIDENCE_SCHEMA" or "LOW_CONFIDENCE_SCHEMA" in statuses:
        return int(DetectSchemaExitCode.LOW_CONFIDENCE)
    return int(DetectSchemaExitCode.OK)


def run_detect_schema(args: argparse.Namespace) -> int:
    if args.max_scan_rows <= 0 or args.max_scan_columns <= 0 or args.max_file_size_mb <= 0:
        LOGGER.error("Лимиты сканирования и размера файла должны быть положительными")
        return int(DetectSchemaExitCode.INVALID_ARGUMENTS)
    if not 0 <= args.min_confidence <= 1:
        LOGGER.error("--min-confidence должен быть в диапазоне 0..1")
        return int(DetectSchemaExitCode.INVALID_ARGUMENTS)
    try:
        candidate = resolve_workbook_candidate(args)
        config = create_default_schema_config()
        config = replace(
            config,
            scan=replace(
                config.scan,
                max_scan_rows=args.max_scan_rows,
                max_scan_columns=args.max_scan_columns,
            ),
            min_sheet_confidence=min(config.min_sheet_confidence, args.min_confidence),
            min_schema_confidence=args.min_confidence,
        )
        with prepared_workbook_session(
            candidate, max_file_size_bytes=args.max_file_size_mb * 1024**2
        ) as session:
            if args.sheet and args.sheet not in session.sheet_names:
                LOGGER.error("Лист не найден: %s", args.sheet)
                return int(DetectSchemaExitCode.SHEET_NOT_FOUND)
            schema = analyze_workbook_schema(
                session, config, sheet_names=(args.sheet,) if args.sheet else None
            )
        save_workbook_schema_json(schema, args.output)
    except ReportProcessorError as exc:
        LOGGER.error("Не удалось распознать структуру: %s", exc)
        if exc.status.value == "INVALID_ARGUMENTS":
            return int(DetectSchemaExitCode.INVALID_ARGUMENTS)
        return int(DetectSchemaExitCode.STRUCTURE_NOT_RECOGNIZED)
    except (SchemaDetectionError, OSError, ValueError) as exc:
        LOGGER.error("Не удалось распознать структуру: %s", exc)
        return int(DetectSchemaExitCode.STRUCTURE_NOT_RECOGNIZED)

    print(f"Файл: {schema.filename}")
    print(f"Проанализировано листов: {len(schema.worksheets)}")
    print(f"Схема сохранена: {args.output}")
    return _exit_code(schema)
