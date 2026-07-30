"""Duplicate-aware, metric-separated aggregation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..config import RulesConfig
from ..models import (
    CATEGORY_DISPLAY_NAMES,
    CATEGORY_ORDER,
    AggregatedDrawingResult,
    DrawingCardResultRow,
    DrawingCode,
    DrawingSourceRow,
    MatchDecision,
    TargetWorkCategory,
)
from ..sources.normalization import build_drawing_code, normalize_text, normalize_unit
from ..statuses import Status


@dataclass(slots=True)
class _Bucket:
    drawing_code: DrawingCode
    quantity_values: list[Decimal]
    cost_values: list[Decimal]
    quantity_rows: list[str]
    cost_rows: list[str]
    units: list[str]
    quantity_rule_ids: list[str]
    cost_rule_ids: list[str]
    quantity_confidences: list[float]
    cost_confidences: list[float]
    quantity_matching_strategies: list[str]
    cost_matching_strategies: list[str]
    warnings: list[str]
    requires_review: bool = False


def _business_key(row: DrawingSourceRow, drawing: DrawingCode) -> tuple[str, ...]:
    return (
        row.object_index_raw or "",
        drawing.group_key,
        normalize_text(row.work_name_raw),
        normalize_unit(row.unit_raw) or "",
        row.source_document_type or "",
    )


def aggregate_rows(
    rows: list[DrawingSourceRow],
    decisions: list[MatchDecision],
    *,
    drawing_code_mode: str,
    strict: bool,
) -> list[AggregatedDrawingResult]:
    decision_map = {decision.row_id: decision for decision in decisions}
    buckets: dict[tuple[str, str, TargetWorkCategory], _Bucket] = {}
    seen_business: dict[tuple[str, ...], str] = {}
    for row in rows:
        decision = decision_map.get(row.row_id)
        if decision is None or decision.category is None:
            continue
        if not row.object_index_raw or not row.drawing_code_raw:
            continue
        drawing = build_drawing_code(row.drawing_code_raw, drawing_code_mode)
        key = _business_key(row, drawing)
        duplicate_of = seen_business.get(key)
        is_duplicate = duplicate_of is not None
        if not is_duplicate:
            seen_business[key] = row.row_id
        group = (row.object_index_raw, drawing.group_key, decision.category)
        bucket = buckets.get(group)
        if bucket is None:
            bucket = _Bucket(drawing, [], [], [], [], [], [], [], [], [], [], [], [])
            buckets[group] = bucket
        if is_duplicate:
            bucket.warnings.append(f"{Status.POSSIBLE_DUPLICATE}:{duplicate_of}:{row.row_id}")
            bucket.requires_review = True
            if strict:
                continue
            # Non-strict still avoids double counting; provenance remains in warning/review.
            continue
        if decision.quantity_decision == "include" and row.remaining_quantity is not None:
            unit = normalize_unit(row.unit_raw)
            if unit:
                bucket.units.append(unit)
            bucket.quantity_values.append(row.remaining_quantity)
            bucket.quantity_rows.append(row.row_id)
            if decision.quantity_rule_id:
                bucket.quantity_rule_ids.append(decision.quantity_rule_id)
            if decision.quantity_confidence is not None:
                bucket.quantity_confidences.append(decision.quantity_confidence)
            if decision.matching_strategy:
                bucket.quantity_matching_strategies.append(decision.matching_strategy)
        elif decision.quantity_decision == "review":
            bucket.requires_review = True
            bucket.warnings.extend(decision.warnings)
        if decision.cost_decision == "include" and row.remaining_total_cost is not None:
            bucket.cost_values.append(row.remaining_total_cost)
            bucket.cost_rows.append(row.row_id)
            if decision.cost_rule_id:
                bucket.cost_rule_ids.append(decision.cost_rule_id)
            if decision.cost_confidence is not None:
                bucket.cost_confidences.append(decision.cost_confidence)
            if decision.matching_strategy:
                bucket.cost_matching_strategies.append(decision.matching_strategy)
        elif decision.cost_decision == "review":
            bucket.requires_review = True
            bucket.warnings.extend(decision.warnings)
    results: list[AggregatedDrawingResult] = []
    for (object_index, _drawing_key, category), bucket in sorted(
        buckets.items(), key=lambda item: (item[0][0], item[0][1], item[0][2].value)
    ):
        unique_units = tuple(dict.fromkeys(bucket.units))
        unit_mismatch = len(unique_units) > 1
        quantity = (
            None
            if unit_mismatch
            else (sum(bucket.quantity_values, Decimal(0)) if bucket.quantity_values else None)
        )
        cost = sum(bucket.cost_values, Decimal(0)) if bucket.cost_values else None
        warnings = list(dict.fromkeys(bucket.warnings))
        if unit_mismatch:
            warnings.append(f"{Status.UNIT_MISMATCH}:{','.join(unique_units)}")
            bucket.requires_review = True
        status = Status.OK.value
        if unit_mismatch:
            status = Status.UNIT_MISMATCH.value
        elif bucket.requires_review:
            status = Status.WARNING.value
        results.append(
            AggregatedDrawingResult(
                object_index=object_index,
                drawing_code=bucket.drawing_code,
                category=category,
                unit=unique_units[0] if len(unique_units) == 1 else None,
                quantity=quantity,
                total_cost=cost,
                quantity_rows=tuple(bucket.quantity_rows),
                cost_rows=tuple(bucket.cost_rows),
                quantity_rule_id=bucket.quantity_rule_ids[0] if bucket.quantity_rule_ids else None,
                cost_rule_id=bucket.cost_rule_ids[0] if bucket.cost_rule_ids else None,
                quantity_confidence=min(bucket.quantity_confidences)
                if bucket.quantity_confidences
                else None,
                cost_confidence=min(bucket.cost_confidences) if bucket.cost_confidences else None,
                status=status,
                requires_manual_review=bucket.requires_review,
                warnings=tuple(warnings),
                quantity_matching_strategies=tuple(
                    dict.fromkeys(bucket.quantity_matching_strategies)
                ),
                cost_matching_strategies=tuple(dict.fromkeys(bucket.cost_matching_strategies)),
            )
        )
    return results


def build_complete_card_rows(
    source_rows: list[DrawingSourceRow],
    aggregated: list[AggregatedDrawingResult],
    rules: RulesConfig,
    *,
    drawing_code_mode: str,
) -> list[DrawingCardResultRow]:
    drawings: dict[tuple[str, str], DrawingCode] = {}
    for row in source_rows:
        if not row.object_index_raw or not row.drawing_code_raw:
            continue
        drawing = build_drawing_code(row.drawing_code_raw, drawing_code_mode)
        drawings[(row.object_index_raw, drawing.group_key)] = drawing
    result_map = {
        (item.object_index, item.drawing_code.group_key, item.category): item for item in aggregated
    }
    expected_units = {
        rule.category: (rule.expected_units[0] if rule.expected_units else None)
        for rule in rules.categories
    }
    card_rows: list[DrawingCardResultRow] = []
    for (object_index, group_key), drawing in sorted(drawings.items()):
        for category in CATEGORY_ORDER:
            aggregated_item = result_map.get((object_index, group_key, category))
            if aggregated_item is None:
                hint = expected_units.get(category) if rules.allow_template_unit_hint else None
                status = Status.UNIT_FROM_TEMPLATE if hint else Status.VALUE_NOT_FOUND
                card_rows.append(
                    DrawingCardResultRow(
                        object_index=object_index,
                        drawing_code=drawing,
                        category=category,
                        display_name=CATEGORY_DISPLAY_NAMES[category],
                        result_unit=hint,
                        remaining_quantity=None,
                        remaining_total_cost=None,
                        quantity_source_rows=(),
                        cost_source_rows=(),
                        quantity_rule_id=None,
                        cost_rule_id=None,
                        quantity_confidence=None,
                        cost_confidence=None,
                        requires_manual_review=False,
                        status=str(status),
                        warnings=(str(status),),
                    )
                )
                continue
            card_rows.append(
                DrawingCardResultRow(
                    object_index=object_index,
                    drawing_code=drawing,
                    category=category,
                    display_name=CATEGORY_DISPLAY_NAMES[category],
                    result_unit=aggregated_item.unit or expected_units.get(category),
                    remaining_quantity=aggregated_item.quantity,
                    remaining_total_cost=aggregated_item.total_cost,
                    quantity_source_rows=aggregated_item.quantity_rows,
                    cost_source_rows=aggregated_item.cost_rows,
                    quantity_rule_id=aggregated_item.quantity_rule_id,
                    cost_rule_id=aggregated_item.cost_rule_id,
                    quantity_confidence=aggregated_item.quantity_confidence,
                    cost_confidence=aggregated_item.cost_confidence,
                    requires_manual_review=aggregated_item.requires_manual_review,
                    status=aggregated_item.status,
                    warnings=aggregated_item.warnings,
                    quantity_matching_strategies=aggregated_item.quantity_matching_strategies,
                    cost_matching_strategies=aggregated_item.cost_matching_strategies,
                )
            )
    return card_rows
