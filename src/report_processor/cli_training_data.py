from __future__ import annotations

import argparse
import sys
from pathlib import Path

from report_processor.extraction.exceptions import ExtractionSerializationError
from report_processor.storage import StorageError
from report_processor.training_data import (
    TrainingDataConfig,
    load_canonical_rows,
    prepare_training_data,
    save_training_data_jsonl,
)


def add_prepare_training_data_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "prepare-training-data",
        help="Очистить и классифицировать канонические строки",
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="DuckDB или JSONL блока 6",
    )
    parser.add_argument(
        "--input-format",
        choices=("auto", "duckdb", "jsonl"),
        default="auto",
        help="Формат входа; auto использует расширение .duckdb/.jsonl",
    )
    parser.add_argument("--output", required=True, type=Path, help="Выходной JSONL")
    parser.add_argument("--include-non-detail", action="store_true")
    parser.add_argument("--include-outdated", action="store_true")
    parser.add_argument("--include-critical-formula-errors", action="store_true")
    parser.add_argument("--no-deduplicate", action="store_true")
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        default="INFO",
    )


def run_prepare_training_data(args: argparse.Namespace) -> int:
    try:
        if args.output.suffix.casefold() != ".jsonl":
            raise ValueError("Выход блока 7 должен иметь расширение .jsonl")
        input_path = args.input.resolve()
        output_paths = {
            args.output.resolve(),
            args.output.with_suffix(".meta.json").resolve(),
        }
        if input_path in output_paths:
            raise ValueError(
                "Вход блока 7 не должен совпадать с JSONL-результатом "
                "или его файлом метаданных"
            )
        rows = load_canonical_rows(args.input, input_format=args.input_format)
        result = prepare_training_data(
            rows,
            config=TrainingDataConfig(
                include_non_detail_rows=args.include_non_detail,
                include_outdated_rows=args.include_outdated,
                include_critical_formula_errors=args.include_critical_formula_errors,
                deduplicate_exact_rows=not args.no_deduplicate,
            ),
        )
    except (OSError, StorageError, TypeError, ValueError) as exc:
        print(f"Ошибка подготовки данных: {exc}", file=sys.stderr)
        return 9
    try:
        saved = save_training_data_jsonl(result, args.output)
    except ExtractionSerializationError as exc:
        print(f"Ошибка записи подготовленных данных: {exc}", file=sys.stderr)
        return 8

    stats = result.statistics
    print(f"Входных строк: {stats.input_rows}")
    print(f"Подготовлено строк: {stats.output_rows}")
    print(f"Удалено точных дублей: {stats.exact_duplicates_removed}")
    print(f"Коллизий line_id: {stats.line_id_collisions}")
    print(f"Результат: {saved.output_path}")
    print(f"Метаданные: {saved.meta_path}")
    return 0
