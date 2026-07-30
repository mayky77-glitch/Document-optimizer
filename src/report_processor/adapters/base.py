from __future__ import annotations

from typing import Protocol

from report_processor.extraction.models import (
    AdapterSchemaValidation,
    CanonicalSourceRow,
    ExtractedCellValue,
    SourceLocation,
)
from report_processor.extraction.statuses import AdapterValidationStatus
from report_processor.schema import LogicalColumn, SheetType, WorksheetSchema


class SourceAdapter(Protocol):
    supported_sheet_type: SheetType

    def validate_schema(self, schema: WorksheetSchema) -> AdapterSchemaValidation: ...

    def build_raw_row(
        self,
        values: tuple[ExtractedCellValue, ...],
        *,
        source_location: SourceLocation,
    ) -> object: ...

    def map_to_canonical(
        self,
        raw_row: object,
        *,
        document_index: str | None,
        document_period: str | None,
    ) -> CanonicalSourceRow: ...


_FIELD_ALIASES: dict[LogicalColumn, frozenset[str]] = {
    LogicalColumn.WORK_NAME: frozenset({"work_name", "name"}),
    LogicalColumn.POSITION_CODE: frozenset({"position_code", "position", "order"}),
    LogicalColumn.OBJECT_CODE: frozenset({"object_code"}),
    LogicalColumn.OBJECT_NAME: frozenset({"object_name", "object"}),
    LogicalColumn.SUBOBJECT_CODE: frozenset({"subobject_code"}),
    LogicalColumn.SUBOBJECT_NAME: frozenset({"subobject_name", "subobject"}),
    LogicalColumn.CURRENT_PERIOD_QUANTITY: frozenset({"current_period_quantity", "quantity"}),
    LogicalColumn.CURRENT_PERIOD_COST: frozenset({"current_period_cost", "cost"}),
}


def logical_aliases(column: LogicalColumn) -> frozenset[str]:
    return _FIELD_ALIASES.get(column, frozenset({column.value}))


def schema_has_logical(schema: WorksheetSchema, logical: LogicalColumn) -> bool:
    names = {item.logical_column.value for item in schema.columns}
    return bool(names & logical_aliases(logical))


def validate_adapter_schema(
    schema: WorksheetSchema,
    *,
    supported_sheet_type: SheetType,
    required_columns: tuple[LogicalColumn, ...],
    optional_columns: tuple[LogicalColumn, ...],
) -> AdapterSchemaValidation:
    if schema.sheet_type is not supported_sheet_type:
        return AdapterSchemaValidation(
            valid=False,
            missing_required_columns=required_columns,
            missing_optional_columns=optional_columns,
            status=AdapterValidationStatus.WRONG_SHEET_TYPE.value,
            warnings=(f"WRONG_SHEET_TYPE:{schema.sheet_type.value}",),
        )
    if not schema.columns:
        return AdapterSchemaValidation(
            valid=False,
            missing_required_columns=required_columns,
            missing_optional_columns=optional_columns,
            status=AdapterValidationStatus.SCHEMA_INVALID.value,
            warnings=("SCHEMA_HAS_NO_COLUMNS",),
        )
    missing_required = tuple(
        item for item in required_columns if not schema_has_logical(schema, item)
    )
    missing_optional = tuple(
        item for item in optional_columns if not schema_has_logical(schema, item)
    )
    if missing_required:
        status = AdapterValidationStatus.REQUIRED_COLUMNS_MISSING
    elif missing_optional:
        status = AdapterValidationStatus.OPTIONAL_COLUMNS_MISSING
    else:
        status = AdapterValidationStatus.OK
    warnings = tuple(
        [
            *(f"REQUIRED_COLUMN_MISSING:{item.value}" for item in missing_required),
            *(f"OPTIONAL_COLUMN_MISSING:{item.value}" for item in missing_optional),
        ]
    )
    return AdapterSchemaValidation(
        valid=not missing_required,
        missing_required_columns=missing_required,
        missing_optional_columns=missing_optional,
        status=status.value,
        warnings=warnings,
    )
