from __future__ import annotations

from report_processor.adapters.base import validate_adapter_schema
from report_processor.adapters.mapping import (
    cell_problem_warnings,
    merge_warnings,
    parse_numeric_cell,
    parse_text_cell,
)
from report_processor.extraction.models import (
    AdapterSchemaValidation,
    CanonicalSourceRow,
    ExtractedCellValue,
    SourceLocation,
)
from report_processor.schema import LogicalColumn, SheetType, WorksheetSchema

from .mapper import map_ks6a_to_canonical
from .models import KS6ARawRow


class KS6AAdapter:
    supported_sheet_type = SheetType.KS6A
    required_columns = (LogicalColumn.WORK_NAME,)
    optional_columns = (
        LogicalColumn.UNIT,
        LogicalColumn.CURRENT_PERIOD_QUANTITY,
        LogicalColumn.CUMULATIVE_QUANTITY,
        LogicalColumn.CURRENT_PERIOD_COST,
        LogicalColumn.CUMULATIVE_COST,
    )

    def validate_schema(self, schema: WorksheetSchema) -> AdapterSchemaValidation:
        return validate_adapter_schema(
            schema,
            supported_sheet_type=self.supported_sheet_type,
            required_columns=self.required_columns,
            optional_columns=self.optional_columns,
        )

    def build_raw_row(
        self,
        values: tuple[ExtractedCellValue, ...],
        *,
        source_location: SourceLocation,
    ) -> KS6ARawRow:
        object_code, w1 = parse_text_cell(values, "object_code")
        object_name, w2 = parse_text_cell(values, "object_name", "object")
        subobject_code, w3 = parse_text_cell(values, "subobject_code")
        subobject_name, w4 = parse_text_cell(values, "subobject_name", "subobject")
        position, w5 = parse_text_cell(values, "position_code", "position", "order")
        work_name, w6 = parse_text_cell(values, "work_name", "name")
        unit, w7 = parse_text_cell(values, "unit")
        contract_quantity, w8 = parse_numeric_cell(values, "contract_quantity")
        current_quantity, w9 = parse_numeric_cell(values, "current_period_quantity", "quantity")
        cumulative_quantity, w10 = parse_numeric_cell(values, "cumulative_quantity")
        remaining_quantity, w11 = parse_numeric_cell(values, "remaining_quantity")
        unit_price, w12 = parse_numeric_cell(values, "unit_price")
        contract_cost, w13 = parse_numeric_cell(values, "contract_cost")
        current_cost, w14 = parse_numeric_cell(values, "current_period_cost", "cost")
        cumulative_cost, w15 = parse_numeric_cell(values, "cumulative_cost")
        total_cost, w16 = parse_numeric_cell(values, "total_cost")
        basis, w17 = parse_text_cell(values, "basis_code")
        drawing, w18 = parse_text_cell(values, "drawing_code")
        cost_type, w19 = parse_text_cell(values, "cost_type_code")
        warnings = merge_warnings(
            cell_problem_warnings(values),
            w1,
            w2,
            w3,
            w4,
            w5,
            w6,
            w7,
            w8,
            w9,
            w10,
            w11,
            w12,
            w13,
            w14,
            w15,
            w16,
            w17,
            w18,
            w19,
        )
        return KS6ARawRow(
            source_location,
            values,
            object_code,
            object_name,
            subobject_code,
            subobject_name,
            position,
            work_name,
            unit,
            contract_quantity,
            current_quantity,
            cumulative_quantity,
            remaining_quantity,
            unit_price,
            contract_cost,
            current_cost,
            cumulative_cost,
            total_cost,
            basis,
            drawing,
            cost_type,
            warnings,
        )

    def map_to_canonical(
        self,
        raw_row: object,
        *,
        document_index: str | None,
        document_period: str | None,
    ) -> CanonicalSourceRow:
        if not isinstance(raw_row, KS6ARawRow):
            raise TypeError("KS6AAdapter ожидает KS6ARawRow")
        return map_ks6a_to_canonical(
            raw_row,
            document_index=document_index,
            document_period=document_period,
        )
