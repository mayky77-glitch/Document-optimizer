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
class ReviewPacketContext:
    """Exact, privacy-safe fields required before a review packet may fan out."""

    tenant_id: str | None
    project_id: str | None
    normalized_work: str | None
    source_type: str | None
    review_reason: str | None
    proposed_category: str | None
    match_mode: str | None
    unit_compatibility_class: str | None
    transactional_row_role: str | None
    rules_version: str | None
    quantity_resolution_mode: str | None
    cost_resolution_mode: str | None


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
    pivot_id: str = ""
    packet_eligible: bool = True
    match_mode: str | None = None
    unit_compatibility_class: str | None = None
    rules_version: str | None = None
    controlled_difference_fields: tuple[str, ...] = ()


def build_review_clusters(
    rows: Mapping[str, DrawingSourceRow],
    decisions: Mapping[str, MatchDecision],
    *,
    contexts: Mapping[str, ReviewPacketContext] | None = None,
) -> tuple[ReviewCluster, ...]:
    """Group compatible rows, using exact context whenever strict packets are requested."""
    grouped: dict[
        tuple[object, ...], list[tuple[str, MatchDecision, ReviewPacketContext | None, bool]]
    ] = {}
    for row_id, decision in decisions.items():
        row = rows.get(row_id)
        if row is None or not decision.requires_manual_review:
            continue
        hazard = _has_hazard(row, decision)
        reason = _reason_code(decision, hazard)
        context = contexts.get(row_id) if contexts is not None else None
        strict_context = contexts is not None
        eligible = not hazard and (
            not strict_context or _is_complete_context(context, decision, reason)
        )
        if strict_context and context is not None:
            key = _strict_packet_key(context)
        else:
            key = _legacy_packet_key(row_id, row, decision, hazard, reason)
        # Hazard and incomplete strict contexts must never be permitted to fan out.
        if not eligible:
            key = (*key, "singleton", row_id)
        grouped.setdefault(key, []).append((row_id, decision, context, eligible))

    clusters: list[ReviewCluster] = []
    for key, members in grouped.items():
        member_ids = tuple(sorted(row_id for row_id, _decision, _context, _eligible in members))
        identity = "|".join((*map(str, key), *member_ids))
        cluster_id = "cluster-" + sha256(identity.encode()).hexdigest()[:24]
        first_id, first_decision, first_context, eligible = members[0]
        first_row = rows[first_id]
        cluster_name = _cluster_name(first_id, first_row, first_context, contexts is not None)
        confidences = [
            value
            for _row_id, decision, _context, _eligible in members
            for value in (decision.quantity_confidence, decision.cost_confidence)
            if value is not None
        ]
        controlled_difference_fields = _controlled_difference_fields(
            first_context, eligible=eligible, has_hazard=_has_hazard(first_row, first_decision)
        )
        clusters.append(
            ReviewCluster(
                cluster_id=cluster_id,
                member_ids=member_ids,
                name=cluster_name,
                unit=normalize_unit(first_row.unit_raw),
                category=first_decision.category,
                reason_code=_reason_code(first_decision, _has_hazard(first_row, first_decision)),
                confidence=float(min(confidences)) if confidences else 0.0,
                has_hazard=_has_hazard(first_row, first_decision),
                pivot_id=member_ids[0],
                packet_eligible=eligible,
                match_mode=first_context.match_mode if first_context else None,
                unit_compatibility_class=(
                    first_context.unit_compatibility_class if first_context else None
                ),
                rules_version=first_context.rules_version if first_context else None,
                controlled_difference_fields=controlled_difference_fields,
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


def _legacy_packet_key(
    row_id: str,
    row: DrawingSourceRow,
    decision: MatchDecision,
    hazard: bool,
    reason: str,
) -> tuple[object, ...]:
    name = review_group_name(row.work_name_raw)
    if not name:
        name = f"missing-name:{row_id}"
    source_type_key = sha256(normalize_text(row.source_document_type or "").encode()).hexdigest()[
        :16
    ]
    return (
        name,
        normalize_unit(row.unit_raw),
        hazard,
        decision.category.value if decision.category else None,
        decision.quantity_decision,
        decision.cost_decision,
        source_type_key,
        reason,
    )


def _strict_packet_key(context: ReviewPacketContext) -> tuple[str, ...]:
    """Return every approved packet dimension in a fixed, exact order."""
    return (
        context.tenant_id or "",
        context.project_id or "",
        normalize_text(context.normalized_work or ""),
        context.source_type or "",
        context.review_reason or "",
        context.proposed_category or "",
        context.match_mode or "",
        context.unit_compatibility_class or "",
        context.transactional_row_role or "",
        context.rules_version or "",
        context.quantity_resolution_mode or "",
        context.cost_resolution_mode or "",
    )


def _is_complete_context(
    context: ReviewPacketContext | None, decision: MatchDecision, reason: str
) -> bool:
    if context is None:
        return False
    expected_category = decision.category.value if decision.category else None
    return bool(
        context.tenant_id
        and context.project_id
        and normalize_text(context.normalized_work or "")
        and context.source_type
        and context.review_reason == reason
        and context.proposed_category == expected_category
        and context.match_mode
        and context.unit_compatibility_class
        and context.transactional_row_role
        and context.rules_version
        and context.quantity_resolution_mode
        and context.cost_resolution_mode
    )


def _cluster_name(
    row_id: str,
    row: DrawingSourceRow,
    context: ReviewPacketContext | None,
    strict_context: bool,
) -> str:
    if strict_context and context is not None:
        return normalize_text(context.normalized_work or "")
    name = review_group_name(row.work_name_raw)
    return "" if not name or name == f"missing-name:{row_id}" else name


def _controlled_difference_fields(
    context: ReviewPacketContext | None, *, eligible: bool, has_hazard: bool
) -> tuple[str, ...]:
    if has_hazard:
        return ("hazard",)
    if not eligible:
        return ("missing_strict_context",)
    if context and context.unit_compatibility_class == "unit_mismatch":
        return ("normalized_source_unit",)
    return ()


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
