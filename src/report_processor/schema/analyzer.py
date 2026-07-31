"""Thin orchestration for worksheet and workbook structure analysis."""

from __future__ import annotations

import logging
from dataclasses import replace
from itertools import pairwise

from report_processor.excel import DualWorkbookSession
from report_processor.schema.column_resolver import (
    resolve_logical_columns,
    resolve_position_column_from_content,
)
from report_processor.schema.confidence import calculate_schema_confidence
from report_processor.schema.config import SchemaDetectionConfig
from report_processor.schema.exceptions import SchemaDetectionError
from report_processor.schema.header_candidates import find_header_candidates
from report_processor.schema.header_composer import compose_logical_headers
from report_processor.schema.models import (
    HeaderCandidate,
    SheetClassification,
    SheetTypeCandidate,
    WorksheetSchema,
    WorksheetSchemaOverride,
)
from report_processor.schema.overrides import (
    apply_column_overrides,
    validate_worksheet_override,
)
from report_processor.schema.requirements import requirements_for
from report_processor.schema.scan_window import get_cached_merged_ranges, scan_worksheet_window
from report_processor.schema.sheet_classifier import classify_worksheet
from report_processor.schema.table_boundaries import (
    detect_data_start_row,
    detect_table_column_bounds,
)
from report_processor.schema.validation import validate_worksheet_schema

LOGGER = logging.getLogger(__name__)


def _manual_header_candidate(start_row: int, end_row: int) -> HeaderCandidate:
    return HeaderCandidate(
        start_row=start_row,
        end_row=end_row,
        score=1.0,
        nonempty_columns=0,
        text_cell_count=0,
        numeric_cell_count=0,
        matched_aliases=(),
        penalties=(),
        reasons=("manual_override",),
    )


def _choose_header(
    candidates: tuple[HeaderCandidate, ...],
) -> tuple[HeaderCandidate | None, bool]:
    if not candidates:
        return None, False
    top = candidates[0]
    contenders = [
        item
        for item in candidates[1:]
        if top.score - item.score <= 0.025 and abs(top.start_row - item.start_row) >= 2
    ]
    return top, bool(contenders)


def _override_classification(
    classification: SheetClassification,
    override: WorksheetSchemaOverride | None,
) -> SheetClassification:
    if override is None or override.sheet_type is None:
        return classification
    manual = SheetTypeCandidate(override.sheet_type, 1.0, ("manual_override",))
    return replace(
        classification,
        sheet_type=override.sheet_type,
        confidence=1.0,
        name_score=classification.name_score,
        content_score=classification.content_score,
        alternative_types=(manual, *classification.alternative_types),
        status="OK",
        warnings=(*classification.warnings, "MANUAL_OVERRIDE_APPLIED"),
    )


def _schema_status(
    classification: SheetClassification,
    header: HeaderCandidate | None,
    ambiguous_header: bool,
    warnings: tuple[str, ...],
    confidence: float,
    min_confidence: float,
) -> str:
    if classification.status in {"UNKNOWN_SHEET_TYPE", "AMBIGUOUS_SHEET_TYPE"}:
        return classification.status
    if classification.status == "LOW_CONFIDENCE_SHEET_TYPE":
        return "LOW_CONFIDENCE_SCHEMA"
    if header is None:
        return "HEADER_NOT_FOUND"
    if ambiguous_header:
        return "AMBIGUOUS_HEADER"
    if "MISSING_REQUIRED_COLUMNS" in warnings:
        return "MISSING_REQUIRED_COLUMNS"
    if "AMBIGUOUS_COLUMNS" in warnings:
        return "COLUMNS_NOT_RESOLVED"
    if "SCAN_CELL_LIMIT_REACHED" in warnings:
        return "SHEET_SCAN_LIMIT_REACHED"
    if confidence < min_confidence:
        return "LOW_CONFIDENCE_SCHEMA"
    return "OK"


def analyze_worksheet_schema(
    session: DualWorkbookSession,
    sheet_name: str,
    config: SchemaDetectionConfig,
    *,
    override: WorksheetSchemaOverride | None = None,
) -> WorksheetSchema:
    LOGGER.info("Анализ листа: %s", sheet_name)
    scan = scan_worksheet_window(session, sheet_name, config.scan)
    if override:
        override_errors = validate_worksheet_override(
            override,
            sheet_names=session.sheet_names,
            max_column=scan.max_scanned_column,
        )
        if override_errors:
            raise SchemaDetectionError(", ".join(override_errors))
    classification = _override_classification(
        classify_worksheet(session, sheet_name, config, scan=scan),
        override,
    )
    candidates = find_header_candidates(scan, classification, config.headers)
    header, ambiguous_header = _choose_header(candidates)
    if override and override.header_start_row is not None:
        end_row = override.header_end_row or override.header_start_row
        header = _manual_header_candidate(override.header_start_row, end_row)
        ambiguous_header = False

    requirements = requirements_for(classification.sheet_type, config.column_requirements)
    warnings = list(scan.warnings) + list(classification.warnings)
    if ambiguous_header:
        warnings.append("AMBIGUOUS_HEADER")

    headers = ()
    columns = ()
    data_start_row = None
    first_column = None
    last_column = None
    if header is not None:
        merged_ranges = get_cached_merged_ranges(session, sheet_name)
        headers = compose_logical_headers(
            scan,
            merged_ranges,
            start_row=header.start_row,
            end_row=header.end_row,
        )
        columns = resolve_logical_columns(
            headers,
            classification.sheet_type,
            config.column_aliases,
        )
        data_start_row = detect_data_start_row(scan, header_end_row=header.end_row)
        if override and override.data_start_row is not None:
            data_start_row = override.data_start_row
        sampled_values: dict[int, list[object]] = {}
        for cell in scan.cells:
            if data_start_row is not None and cell.row >= data_start_row:
                sampled_values.setdefault(cell.column, []).append(cell.raw_value)
        columns = tuple(
            resolve_position_column_from_content(
                headers,
                {column: tuple(values[:32]) for column, values in sampled_values.items()},
                column,
            )
            if column.logical_column.value == "position_code"
            else column
            for column in columns
        )
        columns = apply_column_overrides(columns, headers, override)
        if data_start_row is None:
            warnings.append("DATA_START_NOT_FOUND")
        first_column, last_column = detect_table_column_bounds(headers, columns)
        resolved_indexes = sorted(
            item.column_index
            for item in columns
            if item.status == "OK" and item.column_index is not None
        )
        if any(right - left > 5 for left, right in pairwise(resolved_indexes)):
            warnings.append("TABLE_COLUMN_GAPS")

    ambiguous_columns = [item for item in columns if item.status == "AMBIGUOUS_COLUMN"]
    if ambiguous_columns:
        warnings.append("AMBIGUOUS_COLUMNS")
    if requirements:
        found = {item.logical_column for item in columns if item.status == "OK"}
        if any(item not in found for item in requirements.required):
            warnings.append("MISSING_REQUIRED_COLUMNS")
    if override:
        warnings.append("MANUAL_OVERRIDE_APPLIED")
    warnings_tuple = tuple(dict.fromkeys(warnings))
    confidence = calculate_schema_confidence(
        classification,
        header,
        columns,
        requirements,
        warnings_tuple,
    )
    status = _schema_status(
        classification,
        header,
        ambiguous_header,
        warnings_tuple,
        confidence,
        config.min_schema_confidence,
    )
    schema = WorksheetSchema(
        sheet_name=sheet_name,
        sheet_type=classification.sheet_type,
        classification=classification,
        header_start_row=header.start_row if header else None,
        header_end_row=header.end_row if header else None,
        data_start_row=data_start_row,
        first_table_column=first_column,
        last_table_column=last_column,
        headers=headers,
        columns=columns,
        confidence=confidence,
        status=status,
        warnings=warnings_tuple,
        manual_overrides=("worksheet",) if override else (),
    )
    issues = validate_worksheet_schema(schema, requirements)
    schema = replace(schema, validation_issues=issues)
    LOGGER.info(
        "Лист %s: тип=%s, заголовок=%s-%s, столбцов=%d, статус=%s",
        sheet_name,
        schema.sheet_type.value,
        schema.header_start_row,
        schema.header_end_row,
        sum(item.status == "OK" for item in schema.columns),
        schema.status,
    )
    return schema
