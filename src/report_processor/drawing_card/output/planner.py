"""Pure, shared plan for metric cells written to a drawing card."""

from __future__ import annotations

from openpyxl.utils import get_column_letter

from ..models import CATEGORY_ORDER, DrawingCardResultRow, ObjectBlockLayout, WriteOperation
from .contract import cost_to_million_rubles

_METRICS = (("unit", 2), ("quantity", 3), ("total_cost", 4))


def plan_write_operations(
    *,
    rows: list[DrawingCardResultRow],
    layouts: list[ObjectBlockLayout],
    run_id: str,
    cost_scale: int,
) -> list[WriteOperation]:
    """Describe every metric-cell write without opening or changing a workbook."""

    rows_by_key = {(row.object_index, row.drawing_code.raw, row.category): row for row in rows}
    operations: list[WriteOperation] = []
    for layout in layouts:
        for block in layout.drawing_code_blocks:
            for category_offset, category in enumerate(CATEGORY_ORDER):
                result = rows_by_key[(layout.object_index, block.drawing_code, category)]
                for metric, column_offset in _METRICS:
                    source_rows, rule_id, confidence, strategies, value = _metric_provenance(
                        result, metric, cost_scale
                    )
                    operations.append(
                        WriteOperation(
                            run_id=run_id,
                            output_sheet=layout.sheet_name,
                            output_cell=(
                                f"{get_column_letter(layout.start_column + column_offset)}"
                                f"{block.start_row + category_offset}"
                            ),
                            object_index=layout.object_index,
                            drawing_code=block.drawing_code,
                            category=category.value,
                            metric=metric,
                            old_value=None,
                            new_value=value,
                            unit=result.result_unit,
                            source_rows=source_rows,
                            rule_id=rule_id,
                            matching_strategy=" + ".join(strategies) or None,
                            confidence=confidence,
                            confirmation_status=(
                                "review_required" if result.requires_manual_review else "automatic"
                            ),
                            warnings=result.warnings,
                            matching_strategies=strategies,
                        )
                    )
    return operations


def _metric_provenance(
    row: DrawingCardResultRow, metric: str, cost_scale: int
) -> tuple[tuple[str, ...], str | None, float | None, tuple[str, ...], object]:
    def strategies_for(metric_value: object, *, template_hint: bool = False) -> tuple[str, ...]:
        stored = (
            row.cost_matching_strategies
            if metric == "total_cost"
            else row.quantity_matching_strategies
        )
        if stored:
            return stored
        if template_hint and metric_value is not None:
            return ("template_unit_hint",)
        return ("no_matching_value",)

    if metric == "total_cost":
        value = (
            None
            if row.remaining_total_cost is None
            else cost_to_million_rubles(row.remaining_total_cost, cost_scale)
        )
        return (
            row.cost_source_rows,
            row.cost_rule_id,
            row.cost_confidence,
            strategies_for(value),
            value,
        )
    if metric == "quantity":
        return (
            row.quantity_source_rows,
            row.quantity_rule_id,
            row.quantity_confidence,
            strategies_for(row.remaining_quantity),
            row.remaining_quantity,
        )
    return (
        row.quantity_source_rows,
        row.quantity_rule_id,
        row.quantity_confidence,
        strategies_for(row.result_unit, template_hint=True),
        row.result_unit,
    )
