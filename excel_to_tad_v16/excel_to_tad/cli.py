"""Аргументы командной строки и терминальный интерактивный режим."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from .manifest import CONVERTER_VERSION


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Преобразовать Excel в оптимизированные Parquet-файлы для Tad. "
            "Если пути не указаны, откроется кроссплатформенный выбор в терминале."
        )
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"excel-to-tad {CONVERTER_VERSION}",
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        help=(
            "Путь к XLSX/XLSM/XLSB-файлу. Если не указан, файл можно "
            "выбрать в терминальном навигаторе."
        ),
    )
    parser.add_argument(
        "output_directory",
        nargs="?",
        help=(
            "Папка, в которой будет создан каталог результата. Если не "
            "указана, папку можно выбрать в терминальном навигаторе."
        ),
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Принудительно выбрать и файл, и папку в терминале.",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Удалить предыдущую папку результата с таким же именем.",
    )
    parser.add_argument(
        "--compression",
        choices=[
            "zstd",
            "snappy",
            "lz4",
            "gzip",
            "brotli",
            "uncompressed",
        ],
        default="zstd",
        help="Сжатие Parquet. По умолчанию: zstd.",
    )
    parser.add_argument(
        "--compression-level",
        type=int,
        default=1,
        help=(
            "Уровень сжатия zstd/gzip/brotli. "
            "По умолчанию: 1 — быстрее на слабых ПК."
        ),
    )
    parser.add_argument(
        "--row-group-size",
        type=int,
        default=100_000,
        help="Размер группы строк Parquet. По умолчанию: 100000.",
    )
    parser.add_argument(
        "--only-detailed-ks2",
        action="store_true",
        help=(
            "Для КС-2 оставить только строки, где помимо наименования "
            "есть единица измерения, количество, цена или стоимость. "
            "По умолчанию сохраняются также строковые заголовки и итоги."
        ),
    )
    parser.add_argument(
        "--keep-csv",
        action="store_true",
        help="Сохранить очищенные CSV рядом с Parquet.",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=0,
        help=(
            "Ограничить число потоков Polars. 0 — автоматически. "
            "Для слабого компьютера можно указать 2."
        ),
    )
    parser.add_argument(
        "--schema-sample-rows",
        type=int,
        default=10_000,
        help=(
            "Параметр сохранён для совместимости CLI. Типы теперь "
            "определяются по всей извлечённой колонке в памяти."
        ),
    )
    parser.add_argument(
        "--strict-ks2",
        action="store_true",
        help=(
            "Завершать обработку листа ошибкой, если его название похоже "
            "на КС-2, но структура не распознана. По умолчанию такой лист "
            "обрабатывается как обычная таблица."
        ),
    )
    parser.add_argument(
        "--no-trim-other-sheets",
        action="store_true",
        help=(
            "Не определять границы таблиц на остальных листах и сохранить "
            "их полностью, как в старых версиях."
        ),
    )
    parser.add_argument(
        "--keep-non-tabular-sheets",
        action="store_true",
        help=(
            "Если на листе не найдена уверенная табличная область, сохранить "
            "его полностью. По умолчанию титульные и нетабличные листы "
            "пропускаются."
        ),
    )
    return parser.parse_args(argv)
