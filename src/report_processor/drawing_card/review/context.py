"""Exact, fail-closed feedback replay helpers for manual-review candidates."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

from ..models import DrawingSourceRow, MatchDecision, TargetWorkCategory
from ..sources.normalization import normalize_text
from .feedback import FeedbackContext, FeedbackStore

_EXCEL_HAZARD_PREFIXES = ("FORMULA", "EXCEL")
_REPLAY_POLICIES = frozenset({"quantity_cost", "quantity_only", "cost_only"})
_MISSING_PROPOSED_CATEGORY = "__none__"
_MISSING_POSITION_PART = "__missing__"


def build_feedback_context(
    row: DrawingSourceRow,
    decision: MatchDecision,
    *,
    tenant_id: str,
    project_id: str,
    input_hashes: tuple[str, ...],
    model_version: str,
    rules_version: str,
) -> FeedbackContext | None:
    """Build the complete row key, returning ``None`` for incomplete candidates."""
    normalized_work = normalize_text(row.work_name_raw)
    if not normalized_work or not decision.matching_strategy:
        return None
    unit_policy = _unit_policy(decision)
    if unit_policy is None:
        return None
    return FeedbackContext(
        tenant_id=tenant_id,
        project_id=project_id,
        normalized_work=normalized_work,
        work_fingerprint=sha256(normalized_work.encode("utf-8")).hexdigest(),
        proposed_category=(
            decision.category.value if decision.category is not None else _MISSING_PROPOSED_CATEGORY
        ),
        contract_position=_contract_position_fingerprint(row),
        match_mode=decision.matching_strategy,
        source_unit=row.unit_raw,
        unit_policy=unit_policy,
        input_hashes=input_hashes,
        model_version=model_version,
        rules_version=rules_version,
        subject_type="row",
        member_ids=(row.row_id,),
    )


def replay_exact_feedback(
    row: DrawingSourceRow,
    decision: MatchDecision,
    *,
    store: FeedbackStore,
    tenant_id: str,
    project_id: str,
    input_hashes: tuple[str, ...],
    model_version: str,
    rules_version: str,
) -> MatchDecision | None:
    """Return an exact replay decision, or ``None`` to retain manual review."""
    if _has_excel_hazard(row, decision):
        return None
    context = build_feedback_context(
        row,
        decision,
        tenant_id=tenant_id,
        project_id=project_id,
        input_hashes=input_hashes,
        model_version=model_version,
        rules_version=rules_version,
    )
    if context is None:
        return None
    entry = store.lookup_exact(context)
    if entry is None:
        return None
    if entry.action in {"confirm", "reclassify"}:
        if entry.selected_category is None or context.unit_policy not in _REPLAY_POLICIES:
            return None
        try:
            category = TargetWorkCategory(entry.selected_category)
        except ValueError:
            return None
        quantity_decision, cost_decision = _policy_decisions(context.unit_policy)
    elif entry.action in {"reject", "exclude"}:
        category = None
        quantity_decision = cost_decision = "exclude"
    else:
        return None
    return replace(
        decision,
        category=category,
        quantity_decision=quantity_decision,
        cost_decision=cost_decision,
        quantity_rule_id="exact-feedback-replay",
        cost_rule_id="exact-feedback-replay",
        quantity_confidence=1.0 if quantity_decision == "include" else None,
        cost_confidence=1.0 if cost_decision == "include" else None,
        matching_strategy="exact_feedback_replay",
        evidence_ids=(entry.event_id,),
        reason="Exact active feedback replay",
        requires_manual_review=False,
        status="OK",
    )


def _unit_policy(decision: MatchDecision) -> str | None:
    if decision.quantity_decision not in {"include", "exclude"}:
        return None
    if decision.cost_decision not in {"include", "exclude"}:
        return None
    if decision.quantity_decision == "exclude" and decision.cost_decision == "include":
        return "cost_only"
    if decision.quantity_decision == "include" and decision.cost_decision == "exclude":
        return "quantity_only"
    if decision.quantity_decision == decision.cost_decision == "include":
        return "quantity_cost"
    return None


def _policy_decisions(policy: str) -> tuple[str, str]:
    if policy == "cost_only":
        return "exclude", "include"
    if policy == "quantity_only":
        return "include", "exclude"
    return "include", "include"


def _has_excel_hazard(row: DrawingSourceRow, decision: MatchDecision) -> bool:
    return any(
        str(warning).upper().startswith(_EXCEL_HAZARD_PREFIXES)
        for warning in (*row.warnings, row.status, *decision.warnings, decision.status)
    )


def _contract_position_fingerprint(row: DrawingSourceRow) -> str:
    """Fingerprint all position identity fields, including explicit absent values."""
    parts = (
        row.object_index_raw,
        row.drawing_code_raw,
        row.position_code_raw,
        row.cost_type_code_raw,
    )
    canonical = "\x1f".join(
        normalize_text(value) if value is not None else _MISSING_POSITION_PART for value in parts
    )
    return f"position:{sha256(canonical.encode('utf-8')).hexdigest()}"
