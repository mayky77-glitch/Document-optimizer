"""Sequential workbook-level orchestration and sheet grouping."""

from __future__ import annotations

import logging
from statistics import fmean

from report_processor.excel import DualWorkbookSession
from report_processor.schema.analyzer import analyze_worksheet_schema
from report_processor.schema.config import SchemaDetectionConfig, create_default_schema_config
from report_processor.schema.exceptions import SchemaDetectionError
from report_processor.schema.models import (
    SheetClassification,
    SheetType,
    WorkbookSchema,
    WorksheetSchema,
    WorksheetSchemaOverride,
)

LOGGER = logging.getLogger(__name__)


def _failed_worksheet_schema(sheet_name: str, message: str) -> WorksheetSchema:
    classification = SheetClassification(
        sheet_name=sheet_name,
        sheet_type=SheetType.UNKNOWN,
        confidence=0.0,
        name_score=0.0,
        content_score=0.0,
        matched_name_markers=(),
        matched_content_markers=(),
        alternative_types=(),
        status="SHEET_SCAN_FAILED",
        warnings=(message,),
    )
    return WorksheetSchema(
        sheet_name=sheet_name,
        sheet_type=SheetType.UNKNOWN,
        classification=classification,
        header_start_row=None,
        header_end_row=None,
        data_start_row=None,
        first_table_column=None,
        last_table_column=None,
        headers=(),
        columns=(),
        confidence=0.0,
        status="SCHEMA_DETECTION_FAILED",
        warnings=(message,),
    )


def _group_sheets(
    worksheets: list[WorksheetSchema],
) -> tuple[dict[str, tuple[str, ...]], dict[str, str | None], tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    for worksheet in worksheets:
        grouped.setdefault(worksheet.sheet_type.value, []).append(worksheet.sheet_name)
    sheets_by_type = {key: tuple(value) for key, value in sorted(grouped.items())}
    primary_sheets: dict[str, str | None] = {}
    warnings: list[str] = []
    for sheet_type, names in sheets_by_type.items():
        primary_sheets[sheet_type] = names[0] if len(names) == 1 else None
        if len(names) > 1 and sheet_type != SheetType.UNKNOWN.value:
            warnings.append(f"MULTIPLE_SHEETS_OF_SAME_TYPE:{sheet_type}")
    return sheets_by_type, primary_sheets, tuple(warnings)


def _workbook_status(
    worksheets: list[WorksheetSchema],
    confidence: float,
    minimum: float,
) -> str:
    if any(item.status == "SCHEMA_DETECTION_FAILED" for item in worksheets):
        return "SCHEMA_DETECTION_FAILED"
    if all(item.status == "OK" for item in worksheets):
        return "OK"
    if confidence < minimum:
        return "LOW_CONFIDENCE_SCHEMA"
    return "WARNING"


def analyze_workbook_schema(
    session: DualWorkbookSession,
    config: SchemaDetectionConfig | None = None,
    *,
    overrides: tuple[WorksheetSchemaOverride, ...] = (),
    sheet_names: tuple[str, ...] | None = None,
) -> WorkbookSchema:
    config = config or create_default_schema_config()
    selected_names = sheet_names or session.sheet_names
    missing = tuple(name for name in selected_names if name not in session.sheet_names)
    if missing:
        raise SchemaDetectionError("Листы не найдены: " + ", ".join(missing))
    override_map = {item.sheet_name: item for item in overrides}
    worksheets: list[WorksheetSchema] = []
    for sheet_name in selected_names:
        try:
            worksheets.append(
                analyze_worksheet_schema(
                    session,
                    sheet_name,
                    config,
                    override=override_map.get(sheet_name),
                )
            )
        except SchemaDetectionError as exc:
            LOGGER.error("Ошибка анализа листа %s: %s", sheet_name, exc)
            worksheets.append(_failed_worksheet_schema(sheet_name, str(exc)))

    sheets_by_type, primary_sheets, warnings = _group_sheets(worksheets)
    confidence = round(fmean(item.confidence for item in worksheets), 4) if worksheets else 0.0
    return WorkbookSchema(
        source_file_id=session.source.original_file_id,
        filename=session.source.local_path.name,
        worksheets=tuple(worksheets),
        sheets_by_type=sheets_by_type,
        primary_sheets=primary_sheets,
        confidence=confidence,
        status=_workbook_status(worksheets, confidence, config.min_schema_confidence),
        warnings=warnings,
    )
