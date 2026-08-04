"""Pure, deterministic Wave 4 pattern-registry lifecycle domain.

This module deliberately plans immutable revisions.  It has no persistence,
runtime application, network, Qdrant, grouping, or admin dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum

from .offline import OutcomeSignature, PatternCandidate, fingerprint
from .pattern_models import (
    ActivationMetadata,
    OwnerApproval,
    PatternContradiction,
    PatternRecord,
    PatternRegistryError,
    PatternRegistryEvent,
    PatternRegistryEventType,
    PatternState,
    PatternVersions,
    RollbackMetadata,
    create_pattern_record,
    create_pattern_registry_event,
    validate_state_transition,
)


class DecisionSource(StrEnum):
    EXACT_FEEDBACK = "exact_feedback"
    ACTIVE_PATTERN = "active_pattern"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class RegistryHistory:
    """One pattern's append-only record and evidence-event chains."""

    records: tuple[PatternRecord, ...]
    events: tuple[PatternRegistryEvent, ...]

    def __post_init__(self) -> None:
        if not self.records or len(self.records) != len(self.events):
            _error("HISTORY_INVALID", "registry history is invalid")
        pattern_id = self.records[0].pattern_id
        previous_record: str | None = None
        previous_event: str | None = None
        for revision, (record, event) in enumerate(
            zip(self.records, self.events, strict=True), start=1
        ):
            if (
                record.pattern_id != pattern_id
                or record.revision != revision
                or record.previous_fingerprint != previous_record
                or event.pattern_id != pattern_id
                or event.revision != revision
                or event.previous_event_fingerprint != previous_event
                or event.payload_fingerprint != record.fingerprint
            ):
                _error("HISTORY_CHAIN_INVALID", "registry history chain is invalid")
            previous_record = record.fingerprint
            previous_event = event.fingerprint

    @property
    def head(self) -> PatternRecord:
        return self.records[-1]

    @property
    def head_event(self) -> PatternRegistryEvent:
        return self.events[-1]


@dataclass(frozen=True, slots=True)
class RegistryOperationPlan:
    """An all-or-nothing append plan for a persistence adapter to execute."""

    operation: str
    expected_heads: tuple[PatternRecord, ...]
    appended_records: tuple[PatternRecord, ...]
    appended_events: tuple[PatternRegistryEvent, ...]

    def __post_init__(self) -> None:
        if self.operation not in {"supersession", "rollback"}:
            _error("PLAN_INVALID", "registry operation plan is invalid")
        if not self.expected_heads or len(self.appended_records) != len(self.appended_events):
            _error("PLAN_INVALID", "registry operation plan is invalid")
        if (
            tuple(sorted(self.expected_heads, key=lambda item: item.pattern_id))
            != self.expected_heads
        ):
            _error("PLAN_INVALID", "registry operation plan heads are invalid")
        if len({item.pattern_id for item in self.expected_heads}) != len(self.expected_heads):
            _error("PLAN_INVALID", "registry operation plan heads are invalid")
        for record, event in zip(self.appended_records, self.appended_events, strict=True):
            if (
                event.pattern_id != record.pattern_id
                or event.payload_fingerprint != record.fingerprint
            ):
                _error("PLAN_INVALID", "registry operation plan evidence is invalid")


@dataclass(frozen=True, slots=True)
class PatternDecision:
    outcome: OutcomeSignature | None
    source: DecisionSource
    pattern_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source, DecisionSource):
            _error("DECISION_INVALID", "pattern decision is invalid")
        if self.outcome is not None and not isinstance(self.outcome, OutcomeSignature):
            _error("DECISION_INVALID", "pattern decision is invalid")
        if self.pattern_ids != tuple(sorted(set(self.pattern_ids))):
            _error("DECISION_INVALID", "pattern decision identities are invalid")
        if self.source is DecisionSource.MANUAL and self.outcome is not None:
            _error("DECISION_INVALID", "manual decision cannot contain an outcome")
        if self.source is not DecisionSource.MANUAL and self.outcome is None:
            _error("DECISION_INVALID", "automatic decision requires an outcome")


def _error(code: str, message: str) -> None:
    raise PatternRegistryError(code, message)


def _candidate(candidate: object) -> PatternCandidate:
    if not isinstance(candidate, PatternCandidate):
        _error("CANDIDATE_INVALID", "pattern candidate is invalid")
    if (
        candidate.record_type != "candidate"
        or candidate.state != "proposed"
        or candidate.descriptive_only is not True
        or candidate.requires_owner_review is not True
    ):
        _error("CANDIDATE_INVALID", "pattern candidate is invalid")
    return candidate


def _expected_head(history: RegistryHistory, expected_head: PatternRecord | str) -> PatternRecord:
    fingerprint_value = (
        expected_head.fingerprint if isinstance(expected_head, PatternRecord) else expected_head
    )
    if not isinstance(fingerprint_value, str) or history.head.fingerprint != fingerprint_value:
        _error("STALE_HEAD", "registry head is stale")
    return history.head


def _record_values(record: PatternRecord, **changes: object) -> dict[str, object]:
    values = {
        field.name: getattr(record, field.name)
        for field in fields(PatternRecord)
        if field.name not in {"fingerprint", "version"}
    }
    values.update(changes)
    return values


def _event(
    record: PatternRecord,
    *,
    event_type: PatternRegistryEventType,
    actor_ref: str,
    previous_event_fingerprint: str | None,
) -> PatternRegistryEvent:
    event_id = fingerprint(
        {
            "pattern_id": record.pattern_id,
            "revision": record.revision,
            "event_type": event_type.value,
            "payload_fingerprint": record.fingerprint,
            "actor_ref": actor_ref,
            "previous_event_fingerprint": previous_event_fingerprint,
        }
    )
    return create_pattern_registry_event(
        event_id=event_id,
        event_type=event_type,
        pattern_id=record.pattern_id,
        revision=record.revision,
        previous_event_fingerprint=previous_event_fingerprint,
        payload_fingerprint=record.fingerprint,
        actor_ref=actor_ref,
    )


def _append(
    history: RegistryHistory,
    record: PatternRecord,
    *,
    event_type: PatternRegistryEventType,
    actor_ref: str,
) -> RegistryHistory:
    if (
        record.pattern_id != history.head.pattern_id
        or record.revision != history.head.revision + 1
        or record.previous_fingerprint != history.head.fingerprint
    ):
        _error("REVISION_CHAIN_INVALID", "registry revision is invalid")
    event = _event(
        record,
        event_type=event_type,
        actor_ref=actor_ref,
        previous_event_fingerprint=history.head_event.fingerprint,
    )
    return RegistryHistory((*history.records, record), (*history.events, event))


def _revision(
    head: PatternRecord,
    *,
    state: PatternState,
    **changes: object,
) -> PatternRecord:
    return create_pattern_record(
        **_record_values(
            head,
            revision=head.revision + 1,
            previous_fingerprint=head.fingerprint,
            state=state,
            **changes,
        )
    )


def _contradictions(value: object) -> tuple[PatternContradiction, ...]:
    if not isinstance(value, tuple) or any(
        not isinstance(item, PatternContradiction) for item in value
    ):
        _error("CONFLICT_EVIDENCE_INVALID", "conflict evidence is invalid")
    if value != tuple(sorted(value, key=lambda item: item.contradiction_id)):
        _error("CONFLICT_EVIDENCE_INVALID", "conflict evidence is invalid")
    if len({item.contradiction_id for item in value}) != len(value):
        _error("CONFLICT_EVIDENCE_INVALID", "conflict evidence is invalid")
    return value


def register_candidate(
    candidate: PatternCandidate, *, versions: PatternVersions, actor_ref: str
) -> RegistryHistory:
    """Turn one validated Wave 3 candidate into its immutable proposed revision."""
    candidate = _candidate(candidate)
    if not isinstance(versions, PatternVersions):
        _error("VERSIONS_INVALID", "pattern versions are invalid")
    record = create_pattern_record(
        pattern_id=candidate.candidate_id,
        candidate_id=candidate.candidate_id,
        candidate_fingerprint=candidate.fingerprint,
        candidate_kind=candidate.kind,
        revision=1,
        previous_fingerprint=None,
        state=PatternState.PROPOSED,
        versions=versions,
        scope=candidate.scope,
        template=candidate.proposal,
        expected_outcome=candidate.expected_outcome,
        support=candidate.support,
        hard_negative_refs=(),
        contradictions=(),
        replay=None,
        owner=None,
        activation=None,
        rollback=None,
        supersedes_pattern_id=None,
        superseded_by_pattern_id=None,
        risk_codes=candidate.risk_codes,
    )
    event = _event(
        record,
        event_type=PatternRegistryEventType.CANDIDATE_REGISTERED,
        actor_ref=actor_ref,
        previous_event_fingerprint=None,
    )
    return RegistryHistory((record,), (event,))


def move_to_shadow(
    history: RegistryHistory, *, expected_head: PatternRecord | str, actor_ref: str
) -> RegistryHistory:
    head = _expected_head(history, expected_head)
    validate_state_transition(head.state, PatternState.SHADOW)
    return _append(
        history,
        _revision(head, state=PatternState.SHADOW),
        event_type=PatternRegistryEventType.STATE_TRANSITION,
        actor_ref=actor_ref,
    )


def add_pre_activation_conflicts(
    history: RegistryHistory,
    *,
    expected_head: PatternRecord | str,
    contradictions: tuple[PatternContradiction, ...],
    actor_ref: str,
) -> RegistryHistory:
    """Append conflict evidence before approval; it cannot promote a pattern."""
    head = _expected_head(history, expected_head)
    if head.state not in {PatternState.PROPOSED, PatternState.SHADOW}:
        _error("CONFLICT_BLOCKED", "pre-activation conflict evidence is not appendable")
    contradictions = _contradictions(contradictions)
    if not contradictions:
        _error("CONFLICT_EVIDENCE_INVALID", "conflict evidence is invalid")
    return _append(
        history,
        _revision(head, state=head.state, contradictions=contradictions),
        event_type=PatternRegistryEventType.STATE_TRANSITION,
        actor_ref=actor_ref,
    )


def approve_head(
    history: RegistryHistory,
    *,
    expected_head: PatternRecord | str,
    owner_ref: str,
    approval_ref: str,
) -> RegistryHistory:
    """Owner approval is bound to the current, conflict-free shadow head."""
    head = _expected_head(history, expected_head)
    validate_state_transition(head.state, PatternState.OWNER_APPROVED)
    if head.contradictions:
        _error("CONFLICT_BLOCKED", "conflicting evidence blocks owner approval")
    next_revision = head.revision + 1
    owner = OwnerApproval(owner_ref, approval_ref, next_revision)
    return _append(
        history,
        _revision(head, state=PatternState.OWNER_APPROVED, owner=owner),
        event_type=PatternRegistryEventType.STATE_TRANSITION,
        actor_ref=owner_ref,
    )


def import_verified_wave5_active(
    history: RegistryHistory,
    *,
    expected_head: PatternRecord | str,
    activation: ActivationMetadata,
    actor_ref: str,
) -> RegistryHistory:
    """The sole Wave 4 boundary that models a verified future Wave 5 import."""
    head = _expected_head(history, expected_head)
    if head.state is not PatternState.OWNER_APPROVED:
        _error("WAVE5_IMPORT_INVALID", "verified Wave 5 import requires owner-approved head")
    if head.contradictions:
        _error("CONFLICT_BLOCKED", "conflicting evidence blocks Wave 5 import")
    if not isinstance(activation, ActivationMetadata) or activation.revision != head.revision + 1:
        _error("WAVE5_IMPORT_INVALID", "verified Wave 5 import metadata is invalid")
    # Keep the public transition guard authoritative: ordinary activation fails.
    try:
        validate_state_transition(head.state, PatternState.ACTIVE)
    except PatternRegistryError as exc:
        if exc.code != "WAVE5_REQUIRED":
            raise
    return _append(
        history,
        _revision(head, state=PatternState.ACTIVE, activation=activation),
        event_type=PatternRegistryEventType.WAVE5_VERIFIED_IMPORT,
        actor_ref=actor_ref,
    )


def suspend_active_for_conflict(
    history: RegistryHistory,
    *,
    expected_head: PatternRecord | str,
    contradictions: tuple[PatternContradiction, ...],
    actor_ref: str,
) -> RegistryHistory:
    head = _expected_head(history, expected_head)
    validate_state_transition(head.state, PatternState.SUSPENDED)
    contradictions = _contradictions(contradictions)
    if not contradictions:
        _error("CONFLICT_EVIDENCE_INVALID", "conflict evidence is invalid")
    return _append(
        history,
        _revision(head, state=PatternState.SUSPENDED, contradictions=contradictions),
        event_type=PatternRegistryEventType.CONFLICT_SUSPENDED,
        actor_ref=actor_ref,
    )


def retire_head(
    history: RegistryHistory, *, expected_head: PatternRecord | str, actor_ref: str
) -> RegistryHistory:
    head = _expected_head(history, expected_head)
    validate_state_transition(head.state, PatternState.RETIRED)
    return _append(
        history,
        _revision(head, state=PatternState.RETIRED),
        event_type=PatternRegistryEventType.STATE_TRANSITION,
        actor_ref=actor_ref,
    )


def plan_rollback(
    history: RegistryHistory,
    *,
    expected_head: PatternRecord | str,
    rollback_ref: str,
    rollback_fingerprint: str,
    actor_ref: str,
) -> RegistryOperationPlan:
    """Plan, but do not execute, an atomic active-to-suspended rollback append."""
    head = _expected_head(history, expected_head)
    validate_state_transition(head.state, PatternState.SUSPENDED)
    rollback = RollbackMetadata(rollback_ref, rollback_fingerprint, head.revision)
    record = _revision(head, state=PatternState.SUSPENDED, rollback=rollback)
    event = _event(
        record,
        event_type=PatternRegistryEventType.ROLLED_BACK,
        actor_ref=actor_ref,
        previous_event_fingerprint=history.head_event.fingerprint,
    )
    return RegistryOperationPlan("rollback", (head,), (record,), (event,))


def plan_supersession(
    history: RegistryHistory,
    candidate: PatternCandidate,
    *,
    expected_head: PatternRecord | str,
    versions: PatternVersions,
    actor_ref: str,
) -> RegistryOperationPlan:
    """Plan retirement plus different-ID proposed registration as one atomic operation."""
    head = _expected_head(history, expected_head)
    validate_state_transition(head.state, PatternState.RETIRED)
    candidate = _candidate(candidate)
    if candidate.candidate_id == head.pattern_id:
        _error("SUPERSESSION_INVALID", "supersession requires a different candidate identity")
    if not isinstance(versions, PatternVersions):
        _error("VERSIONS_INVALID", "pattern versions are invalid")
    retired = _revision(
        head,
        state=PatternState.RETIRED,
        superseded_by_pattern_id=candidate.candidate_id,
    )
    replacement = create_pattern_record(
        pattern_id=candidate.candidate_id,
        candidate_id=candidate.candidate_id,
        candidate_fingerprint=candidate.fingerprint,
        candidate_kind=candidate.kind,
        revision=1,
        previous_fingerprint=None,
        state=PatternState.PROPOSED,
        versions=versions,
        scope=candidate.scope,
        template=candidate.proposal,
        expected_outcome=candidate.expected_outcome,
        support=candidate.support,
        hard_negative_refs=(),
        contradictions=(),
        replay=None,
        owner=None,
        activation=None,
        rollback=None,
        supersedes_pattern_id=head.pattern_id,
        superseded_by_pattern_id=None,
        risk_codes=candidate.risk_codes,
    )
    retired_event = _event(
        retired,
        event_type=PatternRegistryEventType.SUPERSEDED,
        actor_ref=actor_ref,
        previous_event_fingerprint=history.head_event.fingerprint,
    )
    replacement_event = _event(
        replacement,
        event_type=PatternRegistryEventType.CANDIDATE_REGISTERED,
        actor_ref=actor_ref,
        previous_event_fingerprint=None,
    )
    records = tuple(sorted((retired, replacement), key=lambda item: item.pattern_id))
    events_by_pattern = {
        retired.pattern_id: retired_event,
        replacement.pattern_id: replacement_event,
    }
    return RegistryOperationPlan(
        "supersession",
        (head,),
        records,
        tuple(events_by_pattern[item.pattern_id] for item in records),
    )


def resolve_precedence(
    *,
    exact_feedback: OutcomeSignature | None,
    matched_records: tuple[PatternRecord, ...],
    current_versions: PatternVersions,
    feedback_pattern_id: str | None = None,
) -> PatternDecision:
    """Resolve exact feedback first, then only current-version active pattern outcomes."""
    if exact_feedback is not None and not isinstance(exact_feedback, OutcomeSignature):
        _error("FEEDBACK_INVALID", "exact feedback is invalid")
    if not isinstance(current_versions, PatternVersions):
        _error("VERSIONS_INVALID", "pattern versions are invalid")
    if not isinstance(matched_records, tuple) or any(
        not isinstance(record, PatternRecord) for record in matched_records
    ):
        _error("DECISION_INVALID", "matched pattern records are invalid")
    if feedback_pattern_id is not None and not isinstance(feedback_pattern_id, str):
        _error("FEEDBACK_INVALID", "exact feedback is invalid")
    active = tuple(
        sorted(
            (
                record
                for record in matched_records
                if record.state is PatternState.ACTIVE and record.versions == current_versions
            ),
            key=lambda record: record.pattern_id,
        )
    )
    if feedback_pattern_id is not None and any(
        record.pattern_id == feedback_pattern_id for record in active
    ):
        _error("SELF_TRAINING_FORBIDDEN", "pattern output cannot be its own exact feedback")
    if exact_feedback is not None:
        return PatternDecision(exact_feedback, DecisionSource.EXACT_FEEDBACK, ())
    if not active:
        return PatternDecision(None, DecisionSource.MANUAL, ())
    outcomes = {record.expected_outcome for record in active}
    if None in outcomes or len(outcomes) != 1:
        return PatternDecision(
            None, DecisionSource.MANUAL, tuple(record.pattern_id for record in active)
        )
    outcome = active[0].expected_outcome
    assert outcome is not None
    return PatternDecision(
        outcome, DecisionSource.ACTIVE_PATTERN, tuple(record.pattern_id for record in active)
    )


def resolve_history_precedence(
    *,
    exact_feedback: OutcomeSignature | None,
    matched_histories: tuple[RegistryHistory, ...],
    current_versions: PatternVersions,
    feedback_pattern_id: str | None = None,
) -> PatternDecision:
    """Resolve using only verified history heads, never a stale active revision."""
    if not isinstance(matched_histories, tuple) or any(
        not isinstance(history, RegistryHistory) for history in matched_histories
    ):
        _error("DECISION_INVALID", "matched pattern histories are invalid")
    if len({history.head.pattern_id for history in matched_histories}) != len(matched_histories):
        _error("DECISION_INVALID", "matched pattern histories are invalid")
    return resolve_precedence(
        exact_feedback=exact_feedback,
        matched_records=tuple(history.head for history in matched_histories),
        current_versions=current_versions,
        feedback_pattern_id=feedback_pattern_id,
    )
