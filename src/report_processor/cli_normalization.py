from __future__ import annotations

import argparse
import sys
from pathlib import Path

from report_processor.extraction.exceptions import ExtractionSerializationError
from report_processor.normalization import (
    load_training_rows_jsonl,
    normalize_training_rows,
    save_normalized_rows_jsonl,
)


def add_normalize_rows_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "normalize-rows",
        help="Нормализовать строки блока 7 и сформировать business line_id",
    )
    parser.add_argument("--input", required=True, type=Path, help="JSONL блока 7")
    parser.add_argument("--output", required=True, type=Path, help="JSONL блока 8")
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        default="INFO",
    )


def run_normalize_rows(args: argparse.Namespace) -> int:
    try:
        if args.input.suffix.casefold() != ".jsonl":
            raise ValueError("Вход блока 8 должен иметь расширение .jsonl")
        if args.output.suffix.casefold() != ".jsonl":
            raise ValueError("Выход блока 8 должен иметь расширение .jsonl")
        input_path = args.input.resolve()
        output_paths = {
            args.output.resolve(),
            args.output.with_suffix(".meta.json").resolve(),
        }
        if input_path in output_paths:
            raise ValueError(
                "Вход блока 8 не должен совпадать с JSONL-результатом "
                "или его файлом метаданных"
            )
        rows = load_training_rows_jsonl(args.input)
        result = normalize_training_rows(rows)
    except (OSError, TypeError, ValueError) as exc:
        print(f"Ошибка нормализации данных: {exc}", file=sys.stderr)
        return 9

    try:
        saved = save_normalized_rows_jsonl(result, args.output)
    except ExtractionSerializationError as exc:
        print(f"Ошибка записи нормализованных данных: {exc}", file=sys.stderr)
        return 8

    print(f"Входных строк: {result.statistics.input_rows}")
    print(f"Нормализовано строк: {result.statistics.output_rows}")
    print(f"Коллизий line_id: {result.statistics.line_id_collisions}")
    print(f"Результат: {saved.output_path}")
    print(f"Метаданные: {saved.meta_path}")
    return 0
