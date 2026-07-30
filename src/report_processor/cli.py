"""Командная строка проекта report_processor."""

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from report_processor.domain.exceptions import (
    BrokenArchiveError,
    ManifestWriteError,
    SourceAccessError,
    SourceNotFoundError,
)
from report_processor.domain.models import ManifestSummary
from report_processor.identifiers.manifest_enricher import (
    enrich_manifest_with_document_indexes,
)
from report_processor.inventory.file_manifest import (
    build_file_manifest,
    load_manifest_json,
    save_manifest_json,
)

EXIT_OK = 0
EXIT_SOURCE_NOT_FOUND = 2
EXIT_SOURCE_ACCESS = 3
EXIT_BROKEN_ARCHIVE = 4
EXIT_WRITE_ERROR = 5


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="report-processor")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser("inventory", help="Построить файловый манифест")
    inventory.add_argument("--source", type=Path, required=True, help="Папка, файл или ZIP")
    inventory.add_argument(
        "--output",
        type=Path,
        default=Path("cache/file_manifest.json"),
        help="Путь для JSON-манифеста",
    )
    inventory.add_argument(
        "--extract-indexes",
        action="store_true",
        help="Сразу обогатить новый манифест индексами документов",
    )
    inventory.add_argument(
        "--allow-loose",
        action="store_true",
        help="Искать низкоуверенные индексы с разделителями вместо скобок",
    )
    inventory.add_argument(
        "--recursive",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Рекурсивно обходить каталог (по умолчанию: да)",
    )
    extract = subparsers.add_parser(
        "extract-indexes", help="Обогатить существующий манифест индексами"
    )
    extract.add_argument("--manifest", type=Path, required=True, help="Входной JSON-манифест")
    extract.add_argument("--output", type=Path, required=True, help="Новый JSON-манифест")
    extract.add_argument(
        "--use-parent-paths",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Искать индекс также в каталогах относительного пути",
    )
    extract.add_argument(
        "--allow-loose",
        action="store_true",
        help="Искать низкоуверенные индексы с разделителями вместо скобок",
    )
    extract.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        default="INFO",
    )
    inventory.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        default="INFO",
    )
    return parser


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _print_summary(
    source: Path, output: Path, manifest_summary: ManifestSummary, source_kind: str
) -> None:
    summary = manifest_summary
    files_by_extension = summary.files_by_extension
    document_markers = summary.files_by_document_marker
    excel_extensions = {".xlsx", ".xlsm", ".xls", ".xlsb", ".ods"}
    excel_files = sum(files_by_extension.get(extension, 0) for extension in excel_extensions)

    print(f"Источник: {source}")
    print(f"Тип источника: {source_kind}")
    print(f"Найдено файлов: {summary.total_entries}")
    print(f"Excel-файлов: {excel_files}")
    print(f"КС-6а: {document_markers.get("ks6a", 0)}")
    print(f"КС-2: {document_markers.get("ks2", 0)}")
    print(f"СВВР: {document_markers.get("svvr", 0)}")
    print(f"Допотчётов: {document_markers.get("additional_report", 0)}")
    print(f"Временных файлов: {summary.temporary_files}")
    print(f"Возможных копий: {summary.probable_copies}")
    print(f"Предупреждений: {summary.warnings_count}")
    print(f"Индекс найден: {summary.entries_with_document_index}")
    print(f"Манифест: {output}")


def main(argv: Sequence[str] | None = None) -> int:
    """Запустить CLI и вернуть детерминированный код завершения."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.log_level)

    try:
        if args.command == "extract-indexes":
            manifest = load_manifest_json(args.manifest)
            enriched = enrich_manifest_with_document_indexes(
                manifest,
                use_parent_paths=args.use_parent_paths,
                allow_loose=args.allow_loose,
            )
            save_manifest_json(enriched, args.output)
            _print_summary(args.manifest, args.output, enriched.summary, enriched.source_kind)
            return EXIT_OK

        manifest = build_file_manifest(args.source, recursive=args.recursive)
        if args.extract_indexes:
            manifest = enrich_manifest_with_document_indexes(
                manifest, use_parent_paths=True, allow_loose=args.allow_loose
            )
        save_manifest_json(manifest, args.output)
    except SourceNotFoundError as exc:
        logging.error("%s", exc)
        return EXIT_SOURCE_NOT_FOUND
    except BrokenArchiveError as exc:
        logging.error("%s", exc)
        return EXIT_BROKEN_ARCHIVE
    except SourceAccessError as exc:
        logging.error("%s", exc)
        return EXIT_SOURCE_ACCESS
    except ManifestWriteError as exc:
        logging.error("%s", exc)
        return EXIT_WRITE_ERROR

    _print_summary(args.source, args.output, manifest.summary, manifest.source_kind)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
