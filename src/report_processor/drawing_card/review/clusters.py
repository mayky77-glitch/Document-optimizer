"""Safe, deterministic groups for applying one inline-review decision."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256

from ..matching.matcher import ReviewApproval
from ..models import DrawingSourceRow, MatchDecision, TargetWorkCategory
from ..sources.normalization import normalize_text, normalize_unit
from ..statuses import Status
from .grouping import review_group_name


@dataclass(frozen=True, slots=True)
class ReviewCluster:
    """A cluster identity includes every member, so stale fanout cannot write."""

    cluster_id: str
    member_ids: tuple[str, ...]
    name: str
    unit: str | None
    category: TargetWorkCategory | None
    reason_code: str
    confidence: float
    has_hazard: bool


def build_review_clusters(
    rows: Mapping[str, DrawingSourceRow], decisions: Mapping[str, MatchDecision]
) -> tuple[ReviewCluster, ...]:
    """Group only compatible manual-review rows without exposing source metadata."""
    grouped: dict[tuple[object, ...], list[tuple[str, MatchDecision]]] = {}
    for row_id, decision in decisions.items():
        row = rows.get(row_id)
        if row is None or not decision.requires_manual_review:
            continue
        name = review_group_name(row.work_name_raw)
        if not name:
            # Empty names are deliberately singleton clusters.
            name = f"missing-name:{row_id}"
        unit = normalize_unit(row.unit_raw)
        hazard = _has_hazard(row, decision)
        reason = _reason_code(decision, hazard)
        source_type_key = sha256(
            normalize_text(row.source_document_type or "").encode()
        ).hexdigest()[:16]
        key = (
            name,
            unit,
            hazard,
            decision.category.value if decision.category else None,
            decision.quantity_decision,
            decision.cost_decision,
            source_type_key,
            reason,
        )
        grouped.setdefault(key, []).append((row_id, decision))

    clusters: list[ReviewCluster] = []
    for key, members in grouped.items():
        member_ids = tuple(sorted(row_id for row_id, _decision in members))
        identity = "|".join((*map(str, key), *member_ids))
        cluster_id = "cluster-" + sha256(identity.encode()).hexdigest()[:24]
        first_id, first_decision = members[0]
        first_row = rows[first_id]
        cluster_name = "" if str(key[0]).startswith("missing-name:") else str(key[0])
        confidences = [
            value
            for _row_id, decision in members
            for value in (decision.quantity_confidence, decision.cost_confidence)
            if value is not None
        ]
        clusters.append(
            ReviewCluster(
                cluster_id=cluster_id,
                member_ids=member_ids,
                name=cluster_name,
                unit=normalize_unit(first_row.unit_raw),
                category=first_decision.category,
                reason_code=str(key[-1]),
                confidence=float(min(confidences)) if confidences else 0.0,
                has_hazard=bool(key[2]),
            )
        )
    return tuple(sorted(clusters, key=lambda item: item.cluster_id))


def cluster_approvals(
    cluster: ReviewCluster, action: str, category: str | None
) -> dict[str, ReviewApproval]:
    """Validate the complete action before callers mutate any job state."""
    selected = category or (cluster.category.value if cluster.category else None)
    return {row_id: _approval(row_id, action, selected) for row_id in cluster.member_ids}


def _approval(row_id: str, action: str, category: str | None) -> ReviewApproval:
    from .inline import review_approval

    return review_approval(row_id, action, category)


def _has_hazard(row: DrawingSourceRow, decision: MatchDecision) -> bool:
    unsafe = {Status.FORMULA_WITHOUT_CACHED_VALUE, Status.EXCEL_ERROR}
    return bool(
        unsafe.intersection(row.warnings)
        or decision.status in unsafe
        or unsafe.intersection(decision.warnings)
    )


def _reason_code(decision: MatchDecision, hazard: bool) -> str:
    if hazard:
        return "formula_or_excel_error"
    if Status.UNIT_MISMATCH in decision.warnings:
        return "unit_mismatch"
    if "SEMANTIC_SUGGESTION_NOT_APPLIED" in decision.warnings:
        return "semantic_suggestion"
    if "MULTIPLE_CATEGORY_MATCHES" in decision.warnings:
        return "multiple_categories"
    if decision.matching_strategy == "tiny_model_suggestion":
        return "model_suggestion"
    return "manual_review"
