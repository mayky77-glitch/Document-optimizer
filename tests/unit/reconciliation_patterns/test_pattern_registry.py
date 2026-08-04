"""Focused deterministic tests for the Wave 4 pure registry domain."""

from __future__ import annotations

import ast
import hashlib
from itertools import product
from pathlib import Path

import pytest

from report_processor.reconciliation_patterns import offline
from report_processor.reconciliation_patterns import pattern_models as models
from report_processor.reconciliation_patterns import pattern_registry as registry


def _hash(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


def _versions(model: str = "Model-1.0") -> models.PatternVersions:
    return models.PatternVersions("Parser-1.0", model, "Taxonomy-1.0")


def _candidate(
    name: str = "one", *, outcome: offline.OutcomeSignature | None = None
) -> offline.PatternCandidate:
    scope = offline.PatternScope(
        f"category-{name}", "quantity_cost", "unit", "accept", "object", "doc"
    )
    proposal = offline.IncludeExcludeProposal(f"predicate-{name}", "accept")
    candidate_id = offline.fingerprint(
        {
            "version": offline.PATTERN_CANDIDATE_VERSION,
            "kind": offline.CandidateKind.INCLUDE_EXCLUDE.value,
            "scope": scope,
            "proposal": proposal,
        }
    )
    support = offline.SupportSummary(
        2, 2, 2, 2, 0, tuple(sorted((_hash(name + "-a"), _hash(name + "-b"))))
    )
    risks = ()
    candidate_fingerprint = offline.fingerprint(
        {"candidate_id": candidate_id, "support": support, "risks": risks}
    )
    return offline.PatternCandidate(
        "candidate",
        candidate_id,
        offline.CandidateKind.INCLUDE_EXCLUDE,
        scope,
        proposal,
        outcome or offline.OutcomeSignature("accept", "quantity_cost", f"category-{name}"),
        support,
        risks,
        candidate_fingerprint,
    )


def _history(name: str = "one") -> registry.RegistryHistory:
    return registry.register_candidate(
        _candidate(name), versions=_versions(), actor_ref=_hash("miner")
    )


def _active(
    name: str = "one", *, versions: models.PatternVersions | None = None
) -> registry.RegistryHistory:
    versions = versions or _versions()
    history = registry.register_candidate(
        _candidate(name), versions=versions, actor_ref=_hash("miner")
    )
    history = registry.move_to_shadow(
        history, expected_head=history.head, actor_ref=_hash("shadow")
    )
    history = registry.approve_head(
        history,
        expected_head=history.head,
        owner_ref=_hash("owner"),
        approval_ref=_hash("approval"),
    )
    return registry.import_verified_wave5_active(
        history,
        expected_head=history.head,
        activation=models.ActivationMetadata(
            _hash("activation"), _hash("activation-fp"), 4, _hash("wave5")
        ),
        actor_ref=_hash("wave5-import"),
    )


def _conflict(left: str, right: str, name: str = "conflict") -> models.PatternContradiction:
    left, right = sorted((left, right))
    return models.PatternContradiction(
        _hash(name), models.FeedbackRelation.CANNOT_LINK, left, right, (_hash(name + "-evidence"),)
    )


@pytest.mark.parametrize("from_state,to_state", tuple(product(models.PatternState, repeat=2)))
def test_exact_lifecycle_transition_table(
    from_state: models.PatternState, to_state: models.PatternState
) -> None:
    allowed = {
        (models.PatternState.PROPOSED, models.PatternState.SHADOW),
        (models.PatternState.PROPOSED, models.PatternState.RETIRED),
        (models.PatternState.SHADOW, models.PatternState.OWNER_APPROVED),
        (models.PatternState.SHADOW, models.PatternState.RETIRED),
        (models.PatternState.OWNER_APPROVED, models.PatternState.RETIRED),
        (models.PatternState.ACTIVE, models.PatternState.SUSPENDED),
        (models.PatternState.ACTIVE, models.PatternState.RETIRED),
        (models.PatternState.SUSPENDED, models.PatternState.RETIRED),
    }
    if (from_state, to_state) in allowed:
        models.validate_state_transition(from_state, to_state)
    else:
        with pytest.raises(models.PatternRegistryError) as error:
            models.validate_state_transition(from_state, to_state)
        expected = (
            "WAVE5_REQUIRED"
            if (from_state, to_state)
            == (models.PatternState.OWNER_APPROVED, models.PatternState.ACTIVE)
            else "STATE_TRANSITION_INVALID"
        )
        assert error.value.code == expected


def test_registration_is_deterministic_and_preserves_candidate_identity() -> None:
    candidate = _candidate()
    first = registry.register_candidate(candidate, versions=_versions(), actor_ref=_hash("miner"))
    second = registry.register_candidate(candidate, versions=_versions(), actor_ref=_hash("miner"))
    assert first == second
    assert first.head.pattern_id == candidate.candidate_id
    assert first.head.candidate_fingerprint == candidate.fingerprint
    assert first.head.state is models.PatternState.PROPOSED
    assert first.events[0].event_type is models.PatternRegistryEventType.CANDIDATE_REGISTERED


def test_stale_head_and_owner_approval_are_bound_to_current_shadow_head() -> None:
    history = _history()
    stale = history.head
    history = registry.move_to_shadow(
        history, expected_head=history.head.fingerprint, actor_ref=_hash("shadow")
    )
    with pytest.raises(models.PatternRegistryError) as error:
        registry.approve_head(
            history, expected_head=stale, owner_ref=_hash("owner"), approval_ref=_hash("approval")
        )
    assert error.value.code == "STALE_HEAD"
    approved = registry.approve_head(
        history,
        expected_head=history.head,
        owner_ref=_hash("owner"),
        approval_ref=_hash("approval"),
    )
    assert approved.head.owner and approved.head.owner.approved_revision == approved.head.revision


def test_pre_active_conflict_evidence_is_recorded_but_blocks_owner_approval() -> None:
    history = _history()
    history = registry.move_to_shadow(
        history, expected_head=history.head, actor_ref=_hash("shadow")
    )
    conflict = _conflict(history.head.pattern_id, _hash("other"))
    blocked = registry.add_pre_activation_conflicts(
        history, expected_head=history.head, contradictions=(conflict,), actor_ref=_hash("evidence")
    )
    assert blocked.head.state is models.PatternState.SHADOW
    assert blocked.head.contradictions == (conflict,)
    with pytest.raises(models.PatternRegistryError) as error:
        registry.approve_head(
            blocked,
            expected_head=blocked.head,
            owner_ref=_hash("owner"),
            approval_ref=_hash("approval"),
        )
    assert error.value.code == "CONFLICT_BLOCKED"


def test_verified_wave5_boundary_is_the_only_activation_path() -> None:
    history = _history()
    history = registry.move_to_shadow(
        history, expected_head=history.head, actor_ref=_hash("shadow")
    )
    history = registry.approve_head(
        history,
        expected_head=history.head,
        owner_ref=_hash("owner"),
        approval_ref=_hash("approval"),
    )
    with pytest.raises(models.PatternRegistryError) as error:
        models.validate_state_transition(history.head.state, models.PatternState.ACTIVE)
    assert error.value.code == "WAVE5_REQUIRED"
    activation = models.ActivationMetadata(
        _hash("activation"), _hash("activation-fp"), 4, _hash("wave5")
    )
    active = registry.import_verified_wave5_active(
        history, expected_head=history.head, activation=activation, actor_ref=_hash("wave5-import")
    )
    assert active.head.state is models.PatternState.ACTIVE
    assert active.events[-1].event_type is models.PatternRegistryEventType.WAVE5_VERIFIED_IMPORT


def test_active_conflict_suspends_and_retirement_is_terminal() -> None:
    active = _active()
    conflict = _conflict(active.head.pattern_id, _hash("other"))
    suspended = registry.suspend_active_for_conflict(
        active, expected_head=active.head, contradictions=(conflict,), actor_ref=_hash("evidence")
    )
    assert suspended.head.state is models.PatternState.SUSPENDED
    retired = registry.retire_head(
        suspended, expected_head=suspended.head, actor_ref=_hash("retire")
    )
    assert retired.head.state is models.PatternState.RETIRED
    with pytest.raises(models.PatternRegistryError) as error:
        registry.move_to_shadow(retired, expected_head=retired.head, actor_ref=_hash("bad"))
    assert error.value.code == "STATE_TRANSITION_INVALID"


def test_supersession_plan_is_atomic_and_creates_a_different_proposed_identity() -> None:
    history = _history("old")
    plan = registry.plan_supersession(
        history,
        _candidate("replacement"),
        expected_head=history.head,
        versions=_versions(),
        actor_ref=_hash("supersede"),
    )
    by_id = {record.pattern_id: record for record in plan.appended_records}
    old = by_id[history.head.pattern_id]
    replacement = next(
        record for record in plan.appended_records if record.pattern_id != old.pattern_id
    )
    assert plan.operation == "supersession"
    assert old.state is models.PatternState.RETIRED
    assert old.superseded_by_pattern_id == replacement.pattern_id
    assert replacement.state is models.PatternState.PROPOSED
    assert replacement.supersedes_pattern_id == old.pattern_id
    assert {event.event_type for event in plan.appended_events} == {
        models.PatternRegistryEventType.SUPERSEDED,
        models.PatternRegistryEventType.CANDIDATE_REGISTERED,
    }


def test_rollback_plan_is_atomic_active_to_suspended_without_history_mutation() -> None:
    history = _active()
    plan = registry.plan_rollback(
        history,
        expected_head=history.head,
        rollback_ref=_hash("rollback"),
        rollback_fingerprint=_hash("rollback-fp"),
        actor_ref=_hash("actor"),
    )
    assert plan.operation == "rollback"
    assert history.head.state is models.PatternState.ACTIVE
    rollback = plan.appended_records[0]
    assert rollback.state is models.PatternState.SUSPENDED
    assert rollback.rollback and rollback.rollback.source_revision == history.head.revision
    assert plan.appended_events[0].event_type is models.PatternRegistryEventType.ROLLED_BACK


def test_exact_feedback_precedence_current_version_active_only_and_conflicts_manual() -> None:
    current = _versions()
    first = _active("first", versions=current).head
    second = _active("second", versions=current).head
    stale = _active("stale", versions=_versions("Model-2.0")).head
    exact = offline.OutcomeSignature("reject", None, None)
    feedback = registry.resolve_precedence(
        exact_feedback=exact, matched_records=(first, second, stale), current_versions=current
    )
    assert feedback == registry.PatternDecision(exact, registry.DecisionSource.EXACT_FEEDBACK, ())
    active = registry.resolve_precedence(
        exact_feedback=None, matched_records=(first, stale), current_versions=current
    )
    assert active.source is registry.DecisionSource.ACTIVE_PATTERN
    assert active.outcome == first.expected_outcome
    assert active.pattern_ids == (first.pattern_id,)
    conflict = registry.resolve_precedence(
        exact_feedback=None, matched_records=(first, second), current_versions=current
    )
    assert conflict.source is registry.DecisionSource.MANUAL
    assert conflict.outcome is None


def test_self_training_is_forbidden_even_when_exact_feedback_is_available() -> None:
    active = _active().head
    with pytest.raises(models.PatternRegistryError) as error:
        registry.resolve_precedence(
            exact_feedback=offline.OutcomeSignature("reject", None, None),
            matched_records=(active,),
            current_versions=_versions(),
            feedback_pattern_id=active.pattern_id,
        )
    assert error.value.code == "SELF_TRAINING_FORBIDDEN"


def test_history_precedence_never_uses_a_stale_active_revision() -> None:
    active = _active()
    conflict = _conflict(active.head.pattern_id, _hash("other"))
    suspended = registry.suspend_active_for_conflict(
        active, expected_head=active.head, contradictions=(conflict,), actor_ref=_hash("evidence")
    )
    decision = registry.resolve_history_precedence(
        exact_feedback=None, matched_histories=(suspended,), current_versions=_versions()
    )
    assert decision == registry.PatternDecision(None, registry.DecisionSource.MANUAL, ())


def test_registry_keeps_forbidden_runtime_boundaries_out_of_its_import_graph() -> None:
    source = registry.__file__
    assert source is not None
    module = ast.parse(Path(source).read_text(encoding="utf-8"))
    imported = {
        name.name.split(".")[0]
        for node in ast.walk(module)
        if isinstance(node, ast.Import)
        for name in node.names
    } | {
        node.module.split(".")[0]
        for node in ast.walk(module)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    for forbidden in ("sqlite", "qdrant", "requests", "http", "admin_panel", "grouping"):
        assert forbidden not in imported
