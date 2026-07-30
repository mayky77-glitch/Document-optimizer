"""Read-only real-workbook evidence for the complete Block 12 input path."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path

import pytest
from openpyxl.utils import get_column_letter

from report_processor.business_rules import load_default_rule_set
from report_processor.excel import WorkbookOpenRequest, open_dual_workbook
from report_processor.extraction import ExtractionConfig, extract_supported_workbook_rows
from report_processor.matching import MatchStatus, MatchStrategy, match_rows
from report_processor.materialization.models import MaterializedSource
from report_processor.normalization import normalize_training_rows
from report_processor.schema import (
    ColumnResolution,
    LogicalColumn,
    SheetType,
    WorkbookSchema,
    WorksheetSchema,
    analyze_workbook_schema,
)
from report_processor.target_report import TargetReportReadRequest, read_target_report
from report_processor.training_data import prepare_training_data

_SOURCE_COLUMNS = (
    (LogicalColumn.POSITION_CODE, 2),
    (LogicalColumn.DRAWING_CODE, 5),
    (LogicalColumn.BASIS_CODE, 6),
    (LogicalColumn.WORK_NAME, 7),
    (LogicalColumn.OBJECT_CODE, 8),
    (LogicalColumn.UNIT, 9),
    (LogicalColumn.CURRENT_PERIOD_QUANTITY, 10),
    (LogicalColumn.UNIT_PRICE, 11),
    (LogicalColumn.CURRENT_PERIOD_COST, 12),
)


def _fingerprint(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return hashlib.sha256(path.read_bytes()).hexdigest(), stat.st_size, stat.st_mtime_ns


def _source(path: Path, source_id: str) -> MaterializedSource:
    return MaterializedSource(
        local_path=path,
        original_file_id=source_id,
        original_relative_path=path.name,
        source_kind="file",
        archive_path=None,
        was_extracted=False,
        temporary=False,
        size_bytes=path.stat().st_size,
        extension=path.suffix.casefold(),
        cleanup_required=False,
        warnings=(),
    )


def _reviewed_source_schema(path: Path, source_id: str) -> WorkbookSchema:
    columns = tuple(
        ColumnResolution(
            logical_column=logical,
            column_index=index,
            column_letter=get_column_letter(index),
            header_text=logical.value,
            confidence=1.0,
            matched_rule="reviewed-real-data",
            alternatives=(),
            status="OK",
            is_manual=True,
        )
        for logical, index in _SOURCE_COLUMNS
    )
    worksheet = WorksheetSchema(
        sheet_name="КС-2",
        sheet_type=SheetType.KS2,
        classification=None,
        header_start_row=21,
        header_end_row=23,
        data_start_row=24,
        first_table_column=2,
        last_table_column=12,
        headers=(),
        columns=columns,
        confidence=1.0,
        status="OK",
        manual_overrides=("reviewed-real-data",),
    )
    return WorkbookSchema(
        source_file_id=source_id,
        filename=path.name,
        worksheets=(worksheet,),
        sheets_by_type={SheetType.KS2.value: ("КС-2",)},
        primary_sheets={SheetType.KS2.value: "КС-2"},
        confidence=1.0,
        status="OK",
    )


def _normalized_source_rows(path: Path):
    source_id = f"real-source:{_fingerprint(path)[0]}"
    schema = _reviewed_source_schema(path, source_id)
    with open_dual_workbook(WorkbookOpenRequest(_source(path, source_id))) as session:
        extracted = extract_supported_workbook_rows(
            session,
            schema,
            document_index="0784",
            document_period="2026-07",
            config=ExtractionConfig(max_rows=5_000, max_consecutive_empty_rows=20),
        )
    canonical_rows = tuple(row for result in extracted for row in result.rows)
    training_rows = prepare_training_data(canonical_rows).rows
    return normalize_training_rows(training_rows).rows


def _target_rows(path: Path):
    source_id = f"real-target:{_fingerprint(path)[0]}"
    with open_dual_workbook(WorkbookOpenRequest(_source(path, source_id))) as session:
        schema = analyze_workbook_schema(session)
        result = read_target_report(session, schema, TargetReportReadRequest())
    assert result.status == "OK"
    return result


def _digest(results) -> str:
    payload = [
        {
            "result_id": item.result_id,
            "status": item.status.value,
            "selected": item.selected_candidate.candidate_id if item.selected_candidate else None,
            "candidates": [
                {
                    "id": candidate.candidate_id,
                    "strategies": [strategy.value for strategy in candidate.strategies],
                    "confidence": format(candidate.confidence, "f"),
                    "rules": candidate.rule_ids,
                    "blockers": candidate.blockers,
                    "source": dict(candidate.source_provenance),
                    "target": dict(candidate.target_provenance),
                }
                for candidate in item.candidates
            ],
        }
        for item in results
    ]
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def test_real_workbooks_run_matching_deterministically_without_mutation() -> None:
    source_value = os.environ.get("DOCUMENT_OPTIMIZER_REAL_SOURCE_XLSX")
    target_value = os.environ.get("DOCUMENT_OPTIMIZER_REAL_TARGET_XLSX")
    if not source_value or not target_value:
        pytest.skip("real XLSX paths are not set")
    source_path, target_path = Path(source_value), Path(target_value)
    before = (_fingerprint(source_path), _fingerprint(target_path))

    source_rows = _normalized_source_rows(source_path)
    target_result = _target_rows(target_path)
    rule_validation = load_default_rule_set()
    assert rule_validation.valid and rule_validation.rule_set is not None
    context = {
        "target_source_id": target_result.schema.source_file_id,
        "target_fingerprint": target_result.schema.source_fingerprint.value,
    }
    first = match_rows(source_rows, target_result.rows, rule_validation.rule_set, **context)
    second = match_rows(
        tuple(reversed(source_rows)),
        tuple(reversed(target_result.rows)),
        rule_validation.rule_set,
        **context,
    )

    assert len(source_rows) == 382
    assert len(target_result.rows) == 107
    assert len(first) == len(target_result.rows)
    assert Counter(item.status for item in first) == {
        MatchStatus.MATCHED: 1,
        MatchStatus.AMBIGUOUS: 5,
        MatchStatus.UNMATCHED: 101,
    }
    assert sum(len(item.candidates) for item in first) == 35
    assert sum(item.selected_candidate is not None for item in first) == 1
    assert _digest(first) == "ecfc6fedfc2c3797ab84c769ec9ddd32a16efb69f61964e2cf43122e283106d3"
    assert _digest(first) == _digest(second)
    assert all(
        item.selected_candidate is None for item in first if item.status is MatchStatus.AMBIGUOUS
    )
    assert all(
        item.selected_candidate.strategy is not MatchStrategy.FUZZY_REVIEW
        for item in first
        if item.selected_candidate is not None
    )
    assert all(
        {
            "source_file_id",
            "source_sheet",
            "source_row",
            "source_row_id",
        }
        <= candidate.source_provenance.keys()
        and {"target_source_id", "sheet_name", "row_number", "target_row_id"}
        <= candidate.target_provenance.keys()
        for item in first
        for candidate in item.candidates
    )
    after = (_fingerprint(source_path), _fingerprint(target_path))
    assert after == before
