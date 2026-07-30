"""CLI adapter for canonical row extraction from a block-5 schema."""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace
from pathlib import Path

from report_processor.cli_inspect import resolve_workbook_candidate
from report_processor.extraction import (
    ExtractionConfig,
    build_extraction_metadata,
    create_workbook_extraction_stream,
    extract_supported_workbook_rows,
    load_workbook_schema_json,
    save_extraction_results_json,
    save_rows_jsonl,
)
from report_processor.extraction.exceptions import (
    ExtractionSchemaError,
    ExtractionSerializationError,
)
from report_processor.schema import SheetType
from report_processor.storage import DuckDBStore, StorageError
from report_processor.workflow import prepared_workbook_session

LOGGER = logging.getLogger(__name__)


def add_extract_rows_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("extract-rows", help="Извлечь канонические строки")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifest", type=Path)
    source.add_argument("--selection", type=Path)
    parser.add_argument("--file-id")
    parser.add_argument("--schema", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--sheet")
    parser.add_argument("--sheet-type", choices=tuple(item.value for item in SheetType))
    parser.add_argument("--format", choices=("duckdb", "jsonl", "json"), default="duckdb")
    parser.add_argument("--max-rows", type=int, default=200_000)
    parser.add_argument("--empty-row-limit", type=int, default=20)
    parser.add_argument("--include-empty-rows", action="store_true")
    parser.add_argument("--max-file-size-mb", type=int, default=2048)
    parser.add_argument("--log-level", default="INFO")


def run_extract_rows(args: argparse.Namespace) -> int:
    if args.max_rows < 1 or args.empty_row_limit < 1 or args.max_file_size_mb < 1:
        raise ValueError("Лимиты извлечения должны быть положительными")
    candidate = resolve_workbook_candidate(args)
    try:
        schema = load_workbook_schema_json(args.schema)
    except ExtractionSchemaError as exc:
        print(f"Ошибка схемы: {exc}", file=sys.stderr)
        return 9
    if schema.source_file_id and schema.source_file_id != candidate.file_id:
        raise ValueError("Схема относится к другому файлу")
    worksheets = tuple(
        item
        for item in schema.worksheets
        if (args.sheet is None or item.sheet_name == args.sheet)
        and (args.sheet_type is None or item.sheet_type.value == args.sheet_type)
    )
    schema = replace(schema, worksheets=worksheets)
    config = ExtractionConfig(
        max_rows=args.max_rows,
        max_consecutive_empty_rows=args.empty_row_limit,
        include_empty_rows=args.include_empty_rows,
    )
    index = candidate.entry.document_index
    period = candidate.entry.document_period
    try:
        with prepared_workbook_session(
            candidate, max_file_size_bytes=args.max_file_size_mb * 1024**2
        ) as session:
            if args.format in {"duckdb", "jsonl"}:
                stream = create_workbook_extraction_stream(
                    session,
                    schema,
                    document_index=index.normalized if index else None,
                    document_period=period.normalized if period else None,
                    config=config,
                )
                if args.format == "duckdb":
                    with DuckDBStore(args.output) as store:
                        store.write_rows(stream)
                else:
                    save_rows_jsonl(
                        stream,
                        args.output,
                        metadata_factory=lambda _count: build_extraction_metadata(
                            stream.sheet_results
                        ),
                    )
                results = stream.sheet_results
            else:
                results = extract_supported_workbook_rows(
                    session,
                    schema,
                    document_index=index.normalized if index else None,
                    document_period=period.normalized if period else None,
                    config=config,
                )
                save_extraction_results_json(results, args.output)
    except (ExtractionSerializationError, StorageError) as exc:
        print(f"Ошибка записи извлечения: {exc}", file=sys.stderr)
        return 8
    print(f"Извлечено: {sum(item.extracted_row_count for item in results)}")
    print(f"Результат: {args.output}")
    return 0
