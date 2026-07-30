from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from report_processor.domain.exceptions import ReportProcessorError
from report_processor.domain.models import FileManifestEntry
from report_processor.domain.statuses import StatusCode
from report_processor.excel.cell_reader import read_cell_snapshot
from report_processor.excel.workbook_metadata import collect_worksheet_metadata
from report_processor.inventory.file_manifest import (
    file_manifest_entry_from_dict,
    load_manifest_json,
)
from report_processor.report_serialization import build_inspection_report, save_inspection_report
from report_processor.selection.models import SourceCandidate
from report_processor.workflow import prepared_workbook_session

LOGGER = logging.getLogger(__name__)


def add_inspect_workbook_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "inspect-workbook", help="Безопасно открыть выбранную Excel-книгу"
    )
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--file-id")
    parser.add_argument("--selection", type=Path)
    parser.add_argument("--sheet")
    parser.add_argument("--cell")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-file-size-mb", type=int, default=2048)
    parser.add_argument("--log-level", default="INFO")


def _entry_from_manifest(path: Path, file_id: str) -> FileManifestEntry:
    manifest = load_manifest_json(path)
    for entry in manifest.entries:
        if entry.file_id == file_id:
            return entry
    raise ReportProcessorError(
        StatusCode.SOURCE_FILE_NOT_FOUND,
        f"file_id не найден в манифесте: {file_id}",
    )


def _find_entry_mapping(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    required = {"file_id", "source_root", "relative_path", "filename", "extension"}
    if required.issubset(value):
        return value
    for key in ("entry", "selected", "selected_candidate", "candidate", "source"):
        found = _find_entry_mapping(value.get(key))
        if found is not None:
            return found
    return None


def _entry_from_selection(path: Path) -> FileManifestEntry:
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    entry_mapping = _find_entry_mapping(payload)
    if entry_mapping is None:
        raise ReportProcessorError(
            StatusCode.SOURCE_FILE_NOT_FOUND,
            "JSON выбора не содержит полной записи FileManifestEntry",
        )
    return file_manifest_entry_from_dict(entry_mapping)


def resolve_workbook_candidate(args: argparse.Namespace) -> SourceCandidate:
    manifest_mode = args.manifest is not None or args.file_id is not None
    selection_mode = args.selection is not None
    if manifest_mode == selection_mode:
        raise ReportProcessorError(
            StatusCode.INVALID_ARGUMENTS,
            "Укажите либо --manifest вместе с --file-id, либо только --selection",
        )
    if manifest_mode and (args.manifest is None or not args.file_id):
        raise ReportProcessorError(
            StatusCode.INVALID_ARGUMENTS,
            "Параметры --manifest и --file-id должны использоваться вместе",
        )
    entry = (
        _entry_from_selection(args.selection)
        if selection_mode
        else _entry_from_manifest(args.manifest, args.file_id)
    )
    return SourceCandidate(
        file_id=entry.file_id,
        entry=entry,
        score=0,
        rank=None,
        accepted=True,
        rejection_reasons=(),
        score_components=(),
        warnings=(),
    )


def _print_inspection(session, worksheets, cell_snapshot) -> None:
    metadata = session.metadata
    print(f"Источник: {session.source.original_relative_path}")
    print(f"Тип: {session.source.source_kind}")
    print(f"Формат: {metadata.extension.lstrip('.')}")
    print(f"Размер: {metadata.size_bytes}")
    print(f"Временное извлечение: {'да' if session.source.was_extracted else 'нет'}")
    print(f"Количество листов: {metadata.sheet_count}")
    print("Листы:")
    for worksheet in worksheets:
        print(f"  {worksheet.index}. {worksheet.title} [{worksheet.state}]")
    if cell_snapshot is not None:
        print(f"Лист: {cell_snapshot.sheet_name}")
        print(f"Ячейка: {cell_snapshot.coordinate}")
        print(f"Формульное представление: {cell_snapshot.formula_value}")
        print(f"Сохранённое значение: {cell_snapshot.cached_value}")
        print(f"Тип формульной ячейки: {cell_snapshot.formula_data_type}")
        print(f"Тип сохранённого значения: {cell_snapshot.cached_data_type}")
        print(f"Статус: {cell_snapshot.status}")


def run_inspect_workbook(args: argparse.Namespace) -> int:
    if (args.sheet is None) != (args.cell is None):
        raise ReportProcessorError(
            StatusCode.INVALID_ARGUMENTS,
            "Параметры --sheet и --cell должны использоваться вместе",
        )
    if args.max_file_size_mb <= 0:
        raise ReportProcessorError(
            StatusCode.INVALID_ARGUMENTS,
            "--max-file-size-mb должен быть положительным",
        )

    candidate = resolve_workbook_candidate(args)
    max_bytes = args.max_file_size_mb * 1024**2
    with prepared_workbook_session(candidate, max_file_size_bytes=max_bytes) as session:
        worksheets = collect_worksheet_metadata(session)
        cell_snapshot = (
            read_cell_snapshot(session, args.sheet, args.cell) if args.sheet is not None else None
        )
        _print_inspection(session, worksheets, cell_snapshot)
        if args.output is not None:
            report = build_inspection_report(
                source=session.source,
                workbook=session.metadata,
                worksheets=worksheets,
                cells=(cell_snapshot,) if cell_snapshot is not None else (),
            )
            save_inspection_report(report, args.output)
            print(f"JSON-отчёт: {args.output}")
    LOGGER.info("Итоговый статус: OK")
    return 0
