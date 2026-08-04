"""P6 public regressions for immutable Wave 4 pattern registry models."""

from __future__ import annotations

import dataclasses
import hashlib
import inspect

import pytest

from report_processor.reconciliation_patterns import offline
from report_processor.reconciliation_patterns import pattern_models as models


def _hash(letter: str) -> str:
    return f"sha256:{hashlib.sha256(letter.encode()).hexdigest()}"


def _candidate() -> tuple[
    str, str, offline.PatternScope, offline.IncludeExcludeProposal, offline.SupportSummary
]:
    scope = offline.PatternScope(
        "category", "quantity_cost", "unit", "accept", "object", "document"
    )
    proposal = offline.IncludeExcludeProposal("predicate", "accept")
    candidate_id = offline.fingerprint(
        {
            "version": offline.PATTERN_CANDIDATE_VERSION,
            "kind": "include_exclude",
            "scope": scope,
            "proposal": proposal,
        }
    )
    support = offline.SupportSummary(2, 2, 2, 2, 0, tuple(sorted((_hash("a"), _hash("b")))))
    candidate_fingerprint = offline.fingerprint(
        {"candidate_id": candidate_id, "support": support, "risks": []}
    )
    return candidate_id, candidate_fingerprint, scope, proposal, support


def _record_values(
    *,
    state: models.PatternState = models.PatternState.PROPOSED,
    revision: int = 1,
    previous: str | None = None,
    **extra: object,
) -> dict[str, object]:
    candidate_id, candidate_fingerprint, scope, proposal, support = _candidate()
    values: dict[str, object] = {
        "pattern_id": candidate_id,
        "candidate_id": candidate_id,
        "candidate_fingerprint": candidate_fingerprint,
        "candidate_kind": offline.CandidateKind.INCLUDE_EXCLUDE,
        "revision": revision,
        "previous_fingerprint": previous,
        "state": state,
        "versions": models.PatternVersions("Parser-1.0", "Model-1.0", "Taxonomy-1.0"),
        "scope": scope,
        "template": proposal,
        "expected_outcome": offline.OutcomeSignature("accept", "quantity_cost", "category"),
        "support": support,
        "hard_negative_refs": (),
        "contradictions": (),
        "replay": None,
        "owner": None,
        "activation": None,
        "rollback": None,
        "supersedes_pattern_id": None,
        "superseded_by_pattern_id": None,
        "risk_codes": (),
    }
    values.update(extra)
    if "risk_codes" in extra and "candidate_fingerprint" not in extra:
        values["candidate_fingerprint"] = offline.fingerprint(
            {
                "candidate_id": candidate_id,
                "support": values["support"],
                "risks": values["risk_codes"],
            }
        )
    return values


def _outcome(category: str = "category", mode: str = "quantity_cost") -> offline.OutcomeSignature:
    return offline.OutcomeSignature("accept", mode, category)


def _confirmation(
    letter: str, outcome: offline.OutcomeSignature | None = None
) -> models.FeedbackConfirmation:
    return models.FeedbackConfirmation(
        _hash(f"confirmation-{letter}"),
        _hash(f"document-set-{letter}"),
        _hash(f"apply-{letter}"),
        _hash(f"result-{letter}"),
        outcome or _outcome(),
    )


def _record_for(kind: offline.CandidateKind, template: offline.Proposal) -> models.PatternRecord:
    values = _record_values(candidate_kind=kind, template=template)
    candidate_id = offline.fingerprint(
        {
            "version": offline.PATTERN_CANDIDATE_VERSION,
            "kind": kind.value,
            "scope": values["scope"],
            "proposal": template,
        }
    )
    values["pattern_id"] = candidate_id
    values["candidate_id"] = candidate_id
    values["candidate_fingerprint"] = offline.fingerprint(
        {"candidate_id": candidate_id, "support": values["support"], "risks": values["risk_codes"]}
    )
    return models.create_pattern_record(**values)


def _public_dataclasses() -> tuple[type[object], ...]:
    return tuple(
        value
        for name, value in vars(models).items()
        if not name.startswith("_")
        and inspect.isclass(value)
        and dataclasses.is_dataclass(value)
        and value.__module__ == models.__name__
    )


def test_versions_enums_and_all_public_field_sets_are_frozen() -> None:
    assert (models.PATTERN_REGISTRY_VERSION, models.FEEDBACK_GRAPH_VERSION) == (
        "PatternRegistry-1.0",
        "FeedbackGraph-1.0",
    )
    assert (models.PATTERN_REGISTRY_EVENT_VERSION, models.FEEDBACK_GRAPH_HARD_NEGATIVE_VERSION) == (
        "PatternRegistryEvent-1.0",
        "FeedbackGraphHardNegative-1.0",
    )
    assert models.PATTERN_REGISTRY_STORE_SCHEMA_VERSION == 1
    assert {item.value for item in models.PatternState} == {
        "proposed",
        "shadow",
        "owner_approved",
        "active",
        "suspended",
        "retired",
    }
    assert {item.value for item in models.FeedbackDirection} == {"symmetric", "directional"}
    assert {item.value for item in models.FeedbackReason} == {
        "explicit_authoritative_confirmation",
        "explicit_authoritative_conflict",
    }
    expected = {
        "PatternRecord": {
            "pattern_id",
            "candidate_id",
            "candidate_fingerprint",
            "candidate_kind",
            "revision",
            "previous_fingerprint",
            "state",
            "versions",
            "scope",
            "template",
            "expected_outcome",
            "support",
            "hard_negative_refs",
            "contradictions",
            "replay",
            "owner",
            "activation",
            "rollback",
            "supersedes_pattern_id",
            "superseded_by_pattern_id",
            "risk_codes",
            "fingerprint",
            "version",
        },
        "FeedbackEndpoint": {"pattern_id", "candidate_id", "outcome"},
        "FeedbackProvenance": {
            "confirmations",
            "document_set_refs",
            "apply_fingerprints",
            "result_fingerprints",
        },
        "FeedbackEdge": {
            "edge_id",
            "relation",
            "direction",
            "reason",
            "source",
            "target",
            "provenance",
            "contradiction_ids",
            "fingerprint",
            "version",
        },
        "HardNegativeIndex": {"entries", "fingerprint", "version"},
        "HardNegativeIndexEntry": {"source_pattern_id", "target_pattern_id", "edge_fingerprint"},
    }
    for name, fields in expected.items():
        assert {field.name for field in dataclasses.fields(getattr(models, name))} == fields
    for model in _public_dataclasses():
        assert model.__dataclass_params__.frozen
        assert "__slots__" in vars(model)


def test_full_lifecycle_constructs_future_active_and_rejects_wave4_activation() -> None:
    proposed = models.create_pattern_record(**_record_values())
    shadow = models.create_pattern_record(**_record_values(state=models.PatternState.SHADOW))
    owner = models.OwnerApproval(_hash("c"), _hash("d"), 1)
    approved = models.create_pattern_record(
        **_record_values(state=models.PatternState.OWNER_APPROVED, owner=owner)
    )
    assert {record.state for record in (proposed, shadow, approved)} == {
        models.PatternState.PROPOSED,
        models.PatternState.SHADOW,
        models.PatternState.OWNER_APPROVED,
    }
    with pytest.raises(models.PatternRegistryError, match="activation") as error:
        models.validate_state_transition(
            models.PatternState.OWNER_APPROVED, models.PatternState.ACTIVE
        )
    assert error.value.code == "WAVE5_REQUIRED"
    for old, new in (
        (models.PatternState.ACTIVE, models.PatternState.SUSPENDED),
        (models.PatternState.ACTIVE, models.PatternState.RETIRED),
    ):
        models.validate_state_transition(old, new)
    with pytest.raises(models.PatternRegistryError) as error:
        models.validate_state_transition(
            models.PatternState.OWNER_APPROVED, models.PatternState.SUSPENDED
        )
    assert error.value.code == "STATE_TRANSITION_INVALID"


def test_rollback_history_and_owner_approval_revision_are_consistent() -> None:
    initial = models.create_pattern_record(**_record_values())
    rollback = models.create_pattern_record(
        **_record_values(
            state=models.PatternState.SUSPENDED,
            revision=2,
            previous=initial.fingerprint,
            rollback=models.RollbackMetadata(_hash("g"), _hash("h"), 1),
        )
    )
    assert rollback.previous_fingerprint == initial.fingerprint
    assert rollback.rollback and rollback.rollback.source_revision == 1
    with pytest.raises(models.PatternRegistryError) as error:
        models.create_pattern_record(
            **_record_values(
                state=models.PatternState.OWNER_APPROVED,
                owner=models.OwnerApproval(_hash("c"), _hash("d"), 2),
            )
        )
    assert error.value.code == "STATE_METADATA_INVALID"


@pytest.mark.parametrize(
    "mutator",
    [
        lambda values: values.update(pattern_id=_hash("z")),
        lambda values: values.update(candidate_fingerprint=_hash("z")),
        lambda values: values.update(scope=True),
        lambda values: values.update(
            template=offline.IncludeExcludeProposal("predicate", "reject")
        ),
        lambda values: values.update(
            support=offline.SupportSummary(2, 2, 2, 1, 0, (_hash("a"), _hash("b")))
        ),
    ],
)
def test_candidate_tampering_is_rejected_by_direct_constructor(mutator: object) -> None:
    values = _record_values()
    mutator(values)  # type: ignore[operator]
    with pytest.raises(models.PatternRegistryError):
        models.create_pattern_record(**values)


def test_candidate_tampering_is_rejected_by_loader_and_instance_graph_is_recursive_immutable() -> (
    None
):
    record = models.create_pattern_record(**_record_values())
    payload = dataclasses.asdict(record)
    payload["candidate_fingerprint"] = _hash("z")
    with pytest.raises(models.PatternRegistryError):
        models.load_pattern_record(payload)
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.scope = offline.PatternScope()  # type: ignore[misc]
    assert isinstance(record.support.support_refs, tuple)
    assert isinstance(record.risk_codes, tuple)


def test_every_consequential_pattern_field_changes_the_fingerprint() -> None:
    record = models.create_pattern_record(**_record_values())
    changed = models.create_pattern_record(**_record_values(risk_codes=("RISK",)))
    assert record.fingerprint != changed.fingerprint
    hard_negative = models.create_pattern_record(
        **_record_values(hard_negative_refs=(_hash("hard-negative"),))
    )
    assert hard_negative.fingerprint != record.fingerprint
    changed_outcome = models.create_pattern_record(
        **_record_values(expected_outcome=_outcome("changed-category"))
    )
    assert changed_outcome.fingerprint != record.fingerprint


def test_feedback_edges_require_typed_authoritative_relation_semantics() -> None:
    left, right = sorted((_candidate()[0], _hash("z")))
    first, second = _confirmation("a"), _confirmation("b")
    provenance = models.FeedbackProvenance(
        (first, second),
        tuple(sorted((first.document_set_ref, second.document_set_ref))),
        tuple(sorted((first.apply_fingerprint, second.apply_fingerprint))),
        tuple(sorted((first.result_fingerprint, second.result_fingerprint))),
    )
    source = models.FeedbackEndpoint(left, left, _outcome())
    target = models.FeedbackEndpoint(right, right, _outcome())
    edge = models.create_feedback_edge(
        relation=models.FeedbackRelation.MUST_LINK,
        direction=models.FeedbackDirection.SYMMETRIC,
        reason=models.FeedbackReason.EXPLICIT_AUTHORITATIVE_CONFIRMATION,
        source=source,
        target=target,
        provenance=provenance,
        contradiction_ids=(),
    )
    assert edge.source == source and edge.provenance == provenance
    reject_target = models.FeedbackEndpoint(right, right, _outcome("other-category"))
    conflicting_confirmation = _confirmation("c", _outcome("other-category"))
    conflict_confirmations = tuple(
        sorted((first, conflicting_confirmation), key=lambda item: item.confirmation_ref)
    )
    conflict_provenance = models.FeedbackProvenance(
        conflict_confirmations,
        tuple(sorted(item.document_set_ref for item in conflict_confirmations)),
        tuple(sorted(item.apply_fingerprint for item in conflict_confirmations)),
        tuple(sorted(item.result_fingerprint for item in conflict_confirmations)),
    )
    cannot_link = models.create_feedback_edge(
        relation=models.FeedbackRelation.CANNOT_LINK,
        direction=models.FeedbackDirection.SYMMETRIC,
        reason=models.FeedbackReason.EXPLICIT_AUTHORITATIVE_CONFLICT,
        source=source,
        target=reject_target,
        provenance=conflict_provenance,
        contradiction_ids=(),
    )
    assert cannot_link.relation is models.FeedbackRelation.CANNOT_LINK
    hard_negative = models.create_feedback_edge(
        relation=models.FeedbackRelation.HARD_NEGATIVE,
        direction=models.FeedbackDirection.DIRECTIONAL,
        reason=models.FeedbackReason.EXPLICIT_AUTHORITATIVE_CONFLICT,
        source=source,
        target=reject_target,
        provenance=conflict_provenance,
        contradiction_ids=(),
    )
    assert hard_negative.direction is models.FeedbackDirection.DIRECTIONAL
    with pytest.raises(models.PatternRegistryError):
        models.create_feedback_edge(
            relation=models.FeedbackRelation.MUST_LINK,
            direction=models.FeedbackDirection.SYMMETRIC,
            reason=models.FeedbackReason.EXPLICIT_AUTHORITATIVE_CONFIRMATION,
            source=source,
            target=reject_target,
            provenance=provenance,
            contradiction_ids=(),
        )
    with pytest.raises(models.PatternRegistryError):
        models.create_feedback_edge(
            relation=models.FeedbackRelation.HARD_NEGATIVE,
            direction=models.FeedbackDirection.SYMMETRIC,
            reason=models.FeedbackReason.EXPLICIT_AUTHORITATIVE_CONFIRMATION,
            source=source,
            target=target,
            provenance=provenance,
            contradiction_ids=(),
        )
    with pytest.raises(models.PatternRegistryError):
        models.FeedbackProvenance((first,), (), (), ())
    with pytest.raises(models.PatternRegistryError):
        models.FeedbackProvenance((first, {"bad": "mapping"}), (), (), ())  # type: ignore[arg-type]


def test_hard_negative_schema_has_only_logical_hash_metadata() -> None:
    assert not {field.name for field in dataclasses.fields(models.HardNegativeIndex)} & {
        "vector",
        "score",
        "collection",
        "alias",
        "endpoint",
        "tenant",
        "raw_term",
    }


def test_sequential_lifecycle_chain_preserves_approved_provenance() -> None:
    proposed = models.create_pattern_record(**_record_values())
    shadow = models.create_pattern_record(
        **_record_values(
            revision=2, previous=proposed.fingerprint, state=models.PatternState.SHADOW
        )
    )
    approval = models.OwnerApproval(_hash("owner"), _hash("approval"), 3)
    approved = models.create_pattern_record(
        **_record_values(
            revision=3,
            previous=shadow.fingerprint,
            state=models.PatternState.OWNER_APPROVED,
            owner=approval,
        )
    )
    activation = models.ActivationMetadata(
        _hash("activation"), _hash("activation-fp"), 4, _hash("wave5")
    )
    active = models.create_pattern_record(
        **_record_values(
            revision=4,
            previous=approved.fingerprint,
            state=models.PatternState.ACTIVE,
            owner=approval,
            activation=activation,
        )
    )
    suspended = models.create_pattern_record(
        **_record_values(
            revision=5,
            previous=active.fingerprint,
            state=models.PatternState.SUSPENDED,
            owner=approval,
            activation=activation,
            rollback=models.RollbackMetadata(_hash("rollback"), _hash("rollback-fp"), 4),
        )
    )
    retired = models.create_pattern_record(
        **_record_values(
            revision=6,
            previous=suspended.fingerprint,
            state=models.PatternState.RETIRED,
            owner=approval,
            activation=activation,
            rollback=models.RollbackMetadata(_hash("retire"), _hash("retire-fp"), 5),
        )
    )
    assert [
        record.revision for record in (proposed, shadow, approved, active, suspended, retired)
    ] == list(range(1, 7))
    assert retired.owner == approval and retired.activation == activation


@pytest.mark.parametrize(
    ("kind", "template"),
    [
        (
            offline.CandidateKind.SYNONYM_ABBREVIATION,
            offline.SynonymAbbreviationProposal(("alpha", "alpha!")),
        ),
        (
            offline.CandidateKind.SLOT_TEMPLATE,
            offline.SlotTemplateProposal("work <slot>", ("a", "b")),
        ),
        (
            offline.CandidateKind.MUST_LINK_CANNOT_LINK,
            offline.MustLinkCannotLinkProposal("must_link", ("alpha", "beta")),
        ),
    ],
)
def test_loader_accepts_only_exact_scalar_and_mapping_proposal_shapes(
    kind: offline.CandidateKind, template: offline.Proposal
) -> None:
    record = _record_for(kind, template)
    payload = dataclasses.asdict(record)
    payload["template"] = {
        name: list(value) if isinstance(value, tuple) else value
        for name, value in payload["template"].items()
    }
    loaded = models.load_pattern_record(payload)
    assert loaded.template == template
    payload["template"] = {"variants": ["beta", "alpha"]}
    with pytest.raises(models.PatternRegistryError):
        models.load_pattern_record(payload)
