"""Typed configuration and default structural rules."""

from __future__ import annotations

from dataclasses import dataclass

from report_processor.schema.column_aliases import DEFAULT_COLUMN_ALIASES
from report_processor.schema.models import (
    ColumnAliasRule,
    SheetColumnRequirements,
    SheetTypeSignature,
)
from report_processor.schema.requirements import DEFAULT_COLUMN_REQUIREMENTS
from report_processor.schema.signatures import DEFAULT_SHEET_SIGNATURES


@dataclass(frozen=True, slots=True)
class SheetScanConfig:
    max_scan_rows: int = 60
    max_scan_columns: int = 120
    max_nonempty_cells: int = 5_000
    stop_after_empty_rows: int = 15


@dataclass(frozen=True, slots=True)
class HeaderDetectionConfig:
    max_header_depth: int = 4
    min_distinct_columns: int = 3
    min_text_ratio: float = 0.5
    max_header_start_row: int = 50


@dataclass(frozen=True, slots=True)
class SchemaDetectionConfig:
    scan: SheetScanConfig
    headers: HeaderDetectionConfig
    sheet_signatures: tuple[SheetTypeSignature, ...]
    column_aliases: tuple[ColumnAliasRule, ...]
    column_requirements: tuple[SheetColumnRequirements, ...]
    min_sheet_confidence: float = 0.65
    min_schema_confidence: float = 0.70


def create_default_schema_config() -> SchemaDetectionConfig:
    return SchemaDetectionConfig(
        scan=SheetScanConfig(),
        headers=HeaderDetectionConfig(),
        sheet_signatures=DEFAULT_SHEET_SIGNATURES,
        column_aliases=DEFAULT_COLUMN_ALIASES,
        column_requirements=DEFAULT_COLUMN_REQUIREMENTS,
    )
