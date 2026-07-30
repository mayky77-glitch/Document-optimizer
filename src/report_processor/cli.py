"""Командная строка проекта report_processor."""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from report_processor.cli_admin import add_admin_parser, run_admin
from report_processor.cli_business_rules import (
    add_validate_business_rules_parser,
    run_validate_business_rules,
)
from report_processor.cli_extraction import add_extract_rows_parser, run_extract_rows
from report_processor.cli_inspect import add_inspect_workbook_parser, run_inspect_workbook
from report_processor.cli_normalization import add_normalize_rows_parser, run_normalize_rows
from report_processor.cli_process import add_process_parser, run_process
from report_processor.cli_schema import add_detect_schema_parser, run_detect_schema
from report_processor.cli_target_report import (
    add_read_target_report_parser,
    run_read_target_report,
)
from report_processor.cli_training_data import (
    add_prepare_training_data_parser,
    run_prepare_training_data,
)
from report_processor.domain.exceptions import (
    BrokenArchiveError,
    ManifestWriteError,
    ReportProcessorError,
    SourceAccessError,
    SourceNotFoundError,
)
from report_processor.domain.models import ManifestSummary
from report_processor.domain.statuses import StatusCode
from report_processor.identifiers.manifest_enricher import (
    enrich_manifest_with_document_indexes,
)
from report_processor.inventory.file_manifest import (
    build_file_manifest,
    load_manifest_json,
    save_manifest_json,
)
from report_processor.metadata.periods import parse_normalized_period
from report_processor.selection.manifest_enricher import enrich_manifest_with_document_metadata
from report_processor.selection.models import SourceSelectionRequest
from report_processor.selection.selector import select_source_file
from report_processor.selection.serialization import save_selection_result_json

EXIT_OK = 0
EXIT_SOURCE_NOT_FOUND = 2
EXIT_SOURCE_ACCESS = 3
EXIT_BROKEN_ARCHIVE = 4
EXIT_WRITE_ERROR = 5
EXIT_SELECTION_AMBIGUOUS = 3
EXIT_SELECTION_INVALID_REQUEST = 4

_WORKBOOK_EXIT_CODES = {
    StatusCode.SOURCE_FILE_NOT_FOUND: 2,
    StatusCode.ARCHIVE_NOT_FOUND: 2,
    StatusCode.ARCHIVE_ENTRY_NOT_FOUND: 2,
    StatusCode.UNSUPPORTED_EXCEL_FORMAT: 3,
    StatusCode.INVALID_XLSX_CONTAINER: 3,
    StatusCode.UNSAFE_ARCHIVE_PATH: 4,
    StatusCode.BROKEN_ARCHIVE: 5,
    StatusCode.CRC_MISMATCH: 5,
    StatusCode.WORKBOOK_OPEN_FAILED: 6,
    StatusCode.SHEET_NOT_FOUND: 7,
    StatusCode.INVALID_CELL_COORDINATE: 7,
    StatusCode.CELL_READ_FAILED: 7,
    StatusCode.JSON_WRITE_FAILED: 8,
    StatusCode.INVALID_ARGUMENTS: 9,
}


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
    metadata = subparsers.add_parser(
        "enrich-metadata", help="Обогатить существующий манифест периодами и редакциями"
    )
    metadata.add_argument("--manifest", type=Path, required=True)
    metadata.add_argument("--output", type=Path, required=True)
    metadata.add_argument("--use-parent-paths", action=argparse.BooleanOptionalAction, default=True)
    metadata.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        default="INFO",
    )
    selection = subparsers.add_parser("select-source", help="Выбрать файл-источник")
    selection.add_argument("--manifest", type=Path, required=True)
    selection.add_argument("--index", required=True)
    selection.add_argument("--period")
    selection.add_argument("--preferred-types", required=True)
    selection.add_argument("--allowed-types", required=True)
    selection.add_argument("--require-exact-period", action="store_true")
    selection.add_argument(
        "--allow-unknown-period", action=argparse.BooleanOptionalAction, default=True
    )
    selection.add_argument("--include-copies", action="store_true")
    selection.add_argument("--include-outdated", action="store_true")
    selection.add_argument("--include-drafts", action="store_true")
    selection.add_argument("--json-output", type=Path)
    selection.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        default="INFO",
    )
    add_inspect_workbook_parser(subparsers)
    add_detect_schema_parser(subparsers)
    add_extract_rows_parser(subparsers)
    add_prepare_training_data_parser(subparsers)
    add_normalize_rows_parser(subparsers)
    add_read_target_report_parser(subparsers)
    add_validate_business_rules_parser(subparsers)
    add_process_parser(subparsers)
    add_admin_parser(subparsers)
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
    print(f"КС-6а: {document_markers.get('ks6a', 0)}")
    print(f"КС-2: {document_markers.get('ks2', 0)}")
    print(f"СВВР: {document_markers.get('svvr', 0)}")
    print(f"Допотчётов: {document_markers.get('additional_report', 0)}")
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
        if args.command == "inspect-workbook":
            return run_inspect_workbook(args)

        if args.command == "detect-schema":
            return run_detect_schema(args)

        if args.command == "extract-rows":
            return run_extract_rows(args)

        if args.command == "prepare-training-data":
            return run_prepare_training_data(args)

        if args.command == "normalize-rows":
            return run_normalize_rows(args)

        if args.command == "read-target-report":
            return run_read_target_report(args)

        if args.command == "validate-business-rules":
            return run_validate_business_rules(args)

        if args.command == "process":
            return run_process(args)

        if args.command == "admin":
            return run_admin(args)

        if args.command == "enrich-metadata":
            manifest = load_manifest_json(args.manifest)
            enriched = enrich_manifest_with_document_metadata(
                manifest, use_parent_paths=args.use_parent_paths
            )
            save_manifest_json(enriched, args.output)
            _print_summary(args.manifest, args.output, enriched.summary, enriched.source_kind)
            return EXIT_OK

        if args.command == "select-source":
            return _run_select_source(args)

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
    except ReportProcessorError as exc:
        logging.error("Ошибка [%s]: %s", exc.status.value, exc)
        return _WORKBOOK_EXIT_CODES.get(exc.status, 1)
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
    except (ValueError, OSError) as exc:
        logging.error("Ошибка аргументов или ввода: %s", exc)
        return _WORKBOOK_EXIT_CODES[StatusCode.INVALID_ARGUMENTS]

    _print_summary(args.source, args.output, manifest.summary, manifest.source_kind)
    return EXIT_OK


def _run_select_source(args: argparse.Namespace) -> int:
    request = _build_selection_request(args)
    if request is None:
        return EXIT_SELECTION_INVALID_REQUEST
    try:
        manifest = load_manifest_json(args.manifest)
        manifest = enrich_manifest_with_document_indexes(manifest)
        manifest = enrich_manifest_with_document_metadata(manifest)
    except (OSError, ValueError) as exc:
        logging.error("Ошибка загрузки манифеста: %s", exc)
        return EXIT_SOURCE_NOT_FOUND

    result = select_source_file(manifest, request)
    for line in result.explanation:
        print(line)
    if args.json_output is not None:
        try:
            save_selection_result_json(result, request, args.json_output)
        except OSError as exc:
            logging.error("Ошибка записи результата: %s", exc)
            return EXIT_WRITE_ERROR
    if result.status == "OK":
        return EXIT_OK
    if result.status == "MULTIPLE_TOP_CANDIDATES":
        return EXIT_SELECTION_AMBIGUOUS
    return EXIT_SOURCE_NOT_FOUND


def _build_selection_request(args: argparse.Namespace) -> SourceSelectionRequest | None:
    from report_processor.identifiers.document_index import extract_document_index

    index_result = extract_document_index(args.index)
    if index_result.value is None:
        print("Некорректный или неоднозначный индекс.", file=sys.stderr)
        return None
    try:
        period = parse_normalized_period(args.period) if args.period else None
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return None
    allowed = _parse_csv(args.allowed_types)
    if not allowed:
        print("Список разрешённых типов пуст.", file=sys.stderr)
        return None
    return SourceSelectionRequest(
        target_index=index_result.value,
        target_period=period,
        preferred_document_types=_parse_csv(args.preferred_types),
        allowed_document_types=allowed,
        require_exact_period=args.require_exact_period,
        allow_unknown_period=args.allow_unknown_period,
        include_probable_copies=args.include_copies,
        include_outdated=args.include_outdated,
        include_drafts=args.include_drafts,
    )


def _parse_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip().lower() for item in value.split(",") if item.strip())


if __name__ == "__main__":
    raise SystemExit(main())
