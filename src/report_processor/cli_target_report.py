"""CLI adapter for the read-only target-report contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from report_processor.cli_json import write_json
from report_processor.extraction import load_workbook_schema_json
from report_processor.inventory import build_file_manifest
from report_processor.schema import analyze_workbook_schema, create_default_schema_config
from report_processor.selection.models import SourceCandidate
from report_processor.target_report import TargetReportReadRequest, read_target_report
from report_processor.workflow import prepared_workbook_session


def add_read_target_report_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "read-target-report", help="Безопасно прочитать выбранный целевой Excel-отчёт"
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-file-size-mb", type=int, default=2048)
    parser.add_argument("--log-level", default="INFO")


def _candidate(source: Path) -> SourceCandidate:
    manifest = build_file_manifest(source)
    if manifest.source_kind != "file" or len(manifest.entries) != 1:
        raise ValueError("--source должен указывать на один обычный Excel-файл")
    entry = manifest.entries[0]
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


def _schema_payload(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Корень schema JSON должен быть объектом")
    return payload


def run_read_target_report(args: argparse.Namespace) -> int:
    if args.max_file_size_mb <= 0:
        raise ValueError("--max-file-size-mb должен быть положительным")
    candidate = _candidate(args.source)
    payload = _schema_payload(args.schema)
    source_identity = payload.get("source_file_id", payload.get("file_id"))
    allowed_identities = {
        candidate.entry.file_id,
        candidate.entry.filename,
        candidate.entry.relative_path,
    }
    if source_identity and source_identity not in allowed_identities:
        raise ValueError("Схема относится к другому source_file_id")
    with prepared_workbook_session(
        candidate, max_file_size_bytes=args.max_file_size_mb * 1024**2
    ) as session:
        if isinstance(payload.get("worksheets", payload.get("sheets")), list):
            schema = load_workbook_schema_json(args.schema)
        else:
            schema = analyze_workbook_schema(session, create_default_schema_config())
        result = read_target_report(session, schema, TargetReportReadRequest())
    write_json(result, args.output)
    return 0 if result.status == "OK" else 2
