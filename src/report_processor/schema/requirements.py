"""Required and optional logical columns by supported sheet type."""

from report_processor.schema.models import LogicalColumn, SheetColumnRequirements, SheetType

DEFAULT_COLUMN_REQUIREMENTS: tuple[SheetColumnRequirements, ...] = (
    SheetColumnRequirements(
        SheetType.KS6A,
        (LogicalColumn.WORK_NAME, LogicalColumn.UNIT),
        (
            LogicalColumn.POSITION_CODE,
            LogicalColumn.CURRENT_PERIOD_QUANTITY,
            LogicalColumn.CUMULATIVE_QUANTITY,
            LogicalColumn.CURRENT_PERIOD_COST,
            LogicalColumn.CUMULATIVE_COST,
        ),
    ),
    SheetColumnRequirements(
        SheetType.KS2,
        (LogicalColumn.WORK_NAME, LogicalColumn.UNIT),
        (
            LogicalColumn.ROW_NUMBER,
            LogicalColumn.POSITION_CODE,
            LogicalColumn.CURRENT_PERIOD_QUANTITY,
            LogicalColumn.UNIT_PRICE,
            LogicalColumn.CURRENT_PERIOD_COST,
        ),
    ),
    SheetColumnRequirements(
        SheetType.SVVR,
        (LogicalColumn.WORK_NAME, LogicalColumn.CURRENT_PERIOD_QUANTITY),
        (
            LogicalColumn.OBJECT_CODE,
            LogicalColumn.SUBOBJECT_CODE,
            LogicalColumn.POSITION_CODE,
            LogicalColumn.UNIT,
        ),
    ),
    SheetColumnRequirements(
        SheetType.ADDITIONAL_REPORT,
        (LogicalColumn.DOCUMENT_INDEX, LogicalColumn.WORK_NAME, LogicalColumn.UNIT),
        (LogicalColumn.STAGE, LogicalColumn.LIMIT_VALUE),
    ),
)


def requirements_for(
    sheet_type: SheetType,
    requirements: tuple[SheetColumnRequirements, ...] = DEFAULT_COLUMN_REQUIREMENTS,
) -> SheetColumnRequirements | None:
    return next((item for item in requirements if item.sheet_type == sheet_type), None)
