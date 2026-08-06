"""Path-free payload shaping for drawing-card review clusters."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from report_processor.drawing_card.matching.matcher import ReviewApproval
from report_processor.drawing_card.models import (
    CATEGORY_DISPLAY_NAMES,
    DrawingSourceRow,
    TargetWorkCategory,
)
from report_processor.drawing_card.review.clusters import ReviewCluster

_REASON_LABELS = {
    "formula_or_excel_error": (
        "В строке есть формула или ошибка Excel; её нужно проверить отдельно."
    ),
    "manual_review": "Для строки требуется явное решение проверяющего.",
    "model_suggestion": "Категория предложена моделью и требует подтверждения.",
    "multiple_categories": "Для строки подходят несколько категорий работ.",
    "semantic_suggestion": "Семантическая подсказка не применяется без подтверждения.",
    "unit_mismatch": "Единица измерения требует ручной проверки.",
}


def drawing_card_cluster_payload(
    *,
    cluster: ReviewCluster,
    rows: Mapping[str, DrawingSourceRow],
    approvals: Mapping[str, ReviewApproval],
    category_units: Mapping[str, tuple[str, ...]],
) -> dict[str, object]:
    """Serialize a cluster with stable, membership-complete, safe members."""
    selected = _selected_approval(cluster, approvals)
    category = selected.category.value if selected and selected.category else None
    target_category = category or (cluster.category.value if cluster.category else None)
    members = [
        _member_payload(
            row_id,
            rows[row_id],
            version=cluster.cluster_id,
            confidence=cluster.confidence,
            reason=cluster.reason_code,
            selected_category=category,
        )
        for row_id in cluster.member_ids
    ]
    aggregate_total_cost = _aggregate_total_cost(rows, cluster.member_ids)
    decision = (
        {"approve": "approved", "reject": "rejected", "quantity_only": "approved"}.get(
            selected.action, selected.action
        )
        if selected
        else "pending"
    )
    return {
        "cluster_id": cluster.cluster_id,
        # Identity includes the sorted member IDs in ``build_review_clusters``;
        # clients echo it to make changed membership stale.
        "version": cluster.cluster_id,
        "work_name": cluster.name,
        "source_unit": cluster.unit,
        "target_unit": _first_category_unit(category_units, target_category),
        "member_count": len(members),
        "aggregate_total_cost": (
            str(aggregate_total_cost) if aggregate_total_cost is not None else None
        ),
        "members": members,
        "proposed_category": cluster.category.value if cluster.category else None,
        "proposed_category_label": _category_label(cluster.category),
        "selected_category": category,
        "selected_category_label": _category_label(selected.category) if selected else None,
        "confidence": cluster.confidence,
        "reason": cluster.reason_code,
        "reason_label": _reason_label(cluster.reason_code),
        "confidence_explanation": _confidence_explanation(cluster.confidence),
        "packet_eligible": cluster.packet_eligible,
        "singleton": len(members) == 1,
        "hazard": cluster.has_hazard,
        "match_mode": cluster.match_mode,
        "unit_compatibility": cluster.unit_compatibility_class,
        "rules_version": cluster.rules_version,
        "controlled_differences": list(cluster.controlled_difference_fields),
        "decision": decision,
    }


def _selected_approval(
    cluster: ReviewCluster, approvals: Mapping[str, ReviewApproval]
) -> ReviewApproval | None:
    values = [approvals.get(row_id) for row_id in cluster.member_ids]
    first = values[0] if values else None
    if first is None:
        return None
    if all(
        item is not None and item.action == first.action and item.category == first.category
        for item in values
    ):
        return first
    return None


def _member_payload(
    review_id: str,
    row: DrawingSourceRow,
    *,
    version: str,
    confidence: float,
    reason: str,
    selected_category: str | None,
) -> dict[str, str | int | float | None]:
    """Keep the member contract intentionally smaller than source-row data."""
    return {
        "review_id": review_id,
        "version": version,
        "safe_filename": _safe_basename(row.location.filename),
        "sheet_name": row.location.sheet_name,
        "row_number": row.location.row_number,
        "position": row.position_code_raw,
        "drawing_code": row.drawing_code_raw,
        "object_index": row.object_index_raw,
        "work_name": row.work_name_raw or "",
        "source_unit": row.unit_raw,
        "quantity": str(row.remaining_quantity) if row.remaining_quantity is not None else None,
        "total_cost": (
            str(row.remaining_total_cost) if row.remaining_total_cost is not None else None
        ),
        "confidence": confidence,
        "reason": reason,
        "reason_label": _reason_label(reason),
        "selected_category": selected_category,
    }


def _safe_basename(value: str) -> str:
    """Return a filename only, including for Windows-originated source names."""
    return value.replace("\\", "/").rsplit("/", maxsplit=1)[-1]


def _reason_label(reason: str) -> str:
    return _REASON_LABELS.get(reason, "Причина проверки требует решения пользователя.")


def _confidence_explanation(confidence: float) -> str:
    if confidence >= 0.9:
        return "Высокая уверенность, но решение всё равно подтверждает проверяющий."
    if confidence >= 0.7:
        return "Средняя уверенность: проверьте категорию и единицу измерения."
    return "Низкая уверенность: проверьте строку по исходному документу."


def _aggregate_total_cost(
    rows: Mapping[str, DrawingSourceRow], member_ids: tuple[str, ...]
) -> Decimal | None:
    costs = [rows[row_id].remaining_total_cost for row_id in member_ids]
    if not any(cost is not None for cost in costs):
        return None
    return sum(cost or Decimal() for cost in costs)


def _first_category_unit(
    category_units: Mapping[str, tuple[str, ...]], category: str | None
) -> str | None:
    units = category_units.get(category or "", ())
    return units[0] if units else None


def _category_label(category: TargetWorkCategory | None) -> str | None:
    return CATEGORY_DISPLAY_NAMES[category] if category else None
