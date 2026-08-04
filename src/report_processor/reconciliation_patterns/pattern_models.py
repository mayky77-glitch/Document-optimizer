"""Immutable Wave 4 contracts for the private reconciliation pattern registry.

The module is intentionally inert: it describes identities and validates
serialized records, but it neither activates patterns nor touches storage,
network, Qdrant, or the reconciliation runtime.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from enum import StrEnum

from .offline import (
    MAX_SUPPORT_REFS,
    PATTERN_CANDIDATE_VERSION,
    CandidateKind,
    CategorySpecificNormalizationProposal,
    CriticalModifierProposal,
    IncludeExcludeProposal,
    MustLinkCannotLinkProposal,
    OutcomeSignature,
    PatternScope,
    Proposal,
    SlotTemplateProposal,
    SplitMergeProposal,
    SupportSummary,
    SynonymAbbreviationProposal,
    canonical_json_bytes,
    fingerprint,
)

PATTERN_REGISTRY_VERSION = "PatternRegistry-1.0"
FEEDBACK_GRAPH_VERSION = "FeedbackGraph-1.0"
PATTERN_REGISTRY_EVENT_VERSION = "PatternRegistryEvent-1.0"
FEEDBACK_GRAPH_HARD_NEGATIVE_VERSION = "FeedbackGraphHardNegative-1.0"
PATTERN_REGISTRY_STORE_SCHEMA_VERSION = 1

_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_VERSION = re.compile(r"[A-Za-z][A-Za-z0-9_-]*-\d+\.\d+\Z")
_RISK = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")


class PatternRegistryError(ValueError):
    """Stable, privacy-safe public contract failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class PatternState(StrEnum):
    PROPOSED = "proposed"
    SHADOW = "shadow"
    OWNER_APPROVED = "owner_approved"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class FeedbackRelation(StrEnum):
    MUST_LINK = "must_link"
    CANNOT_LINK = "cannot_link"
    HARD_NEGATIVE = "hard_negative"


class FeedbackDirection(StrEnum):
    SYMMETRIC = "symmetric"
    DIRECTIONAL = "directional"


class FeedbackReason(StrEnum):
    EXPLICIT_AUTHORITATIVE_CONFIRMATION = "explicit_authoritative_confirmation"
    EXPLICIT_AUTHORITATIVE_CONFLICT = "explicit_authoritative_conflict"


class PatternRegistryEventType(StrEnum):
    CANDIDATE_REGISTERED = "candidate_registered"
    STATE_TRANSITION = "state_transition"
    CONFLICT_SUSPENDED = "conflict_suspended"
    SUPERSEDED = "superseded"
    ROLLED_BACK = "rolled_back"
    WAVE5_VERIFIED_IMPORT = "wave5_verified_import"


def _error(code: str, message: str) -> None:
    raise PatternRegistryError(code, message)


def _hash(value: object, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        _error("INVALID_FINGERPRINT", "fingerprint is invalid")
    return value


def _version(value: object, *, expected: str | None = None) -> str:
    if not isinstance(value, str) or not _VERSION.fullmatch(value):
        _error("INVALID_VERSION", "version is invalid")
    if expected is not None and value != expected:
        _error("UNSUPPORTED_VERSION", "version is unsupported")
    return value


def _positive_int(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        _error("INVALID_SCHEMA", f"{name} is invalid")
    return value


def _opaque_ref(value: object, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    result = _hash(value)
    assert result is not None
    return result


def _sorted_hashes(value: object, *, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple) or any(not isinstance(item, str) for item in value):
        _error("INVALID_SCHEMA", f"{name} is invalid")
    items = tuple(_hash(item) for item in value)
    if items != tuple(sorted(set(items))):
        _error("INVARIANT_VIOLATION", f"{name} must be sorted and unique")
    return items  # type: ignore[return-value]


def _sorted_risks(value: object) -> tuple[str, ...]:
    if not isinstance(value, tuple) or any(not isinstance(item, str) or not item for item in value):
        _error("INVALID_SCHEMA", "risk codes are invalid")
    if value != tuple(sorted(set(value))):
        _error("INVARIANT_VIOLATION", "risk codes must be sorted and unique")
    return value


def _sorted_issue_codes(value: object) -> tuple[str, ...]:
    if not isinstance(value, tuple) or any(
        not isinstance(item, str) or not _RISK.fullmatch(item) for item in value
    ):
        _error("INVALID_SCHEMA", "integrity issues are invalid")
    if value != tuple(sorted(set(value))):
        _error("INVARIANT_VIOLATION", "integrity issues must be sorted and unique")
    return value


def _plain(value: object) -> object:
    """Internal JSON material; public models never expose mutable containers."""
    if is_dataclass(value):
        return {field.name: _plain(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return tuple(_plain(item) for item in value)
    return value


def _material(value: object, *, exclude: frozenset[str] = frozenset()) -> object:
    if not is_dataclass(value):
        _error("INVALID_SCHEMA", "model material is invalid")
    return {
        field.name: _plain(getattr(value, field.name))
        for field in fields(value)
        if field.name not in exclude
    }


def _canonical_fingerprint(value: object) -> str:
    try:
        _validate_canonical_value(value)
        return fingerprint(value)
    except Exception as exc:  # Wave 3 normalizes JSON failures to a stable error.
        raise PatternRegistryError("INVARIANT_VIOLATION", "canonical material is invalid") from exc


def _validate_recursive(value: object) -> None:
    if isinstance(value, float):
        _error("INVALID_SCHEMA", "floating point values are forbidden")
    if isinstance(value, (dict, list, set, frozenset)):
        _error("INVALID_SCHEMA", "mutable containers are forbidden")
    if isinstance(value, tuple):
        for item in value:
            _validate_recursive(item)
    elif is_dataclass(value):
        for field in fields(value):
            _validate_recursive(getattr(value, field.name))


def _validate_canonical_value(value: object) -> None:
    """Allow mappings only as loader/fingerprint input, never in public models."""
    if isinstance(value, (float, list, set, frozenset)):
        _error("INVALID_SCHEMA", "canonical material is invalid")
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                _error("INVALID_SCHEMA", "canonical material is invalid")
            _validate_canonical_value(item)
    elif isinstance(value, tuple):
        for item in value:
            _validate_canonical_value(item)
    elif is_dataclass(value):
        for field in fields(value):
            _validate_canonical_value(getattr(value, field.name))


def _validate_scope(scope: object) -> PatternScope:
    if not isinstance(scope, PatternScope):
        _error("INVALID_SCHEMA", "pattern scope is invalid")
    if any(
        item is not None and (not isinstance(item, str) or not item)
        for field in fields(scope)
        if (item := getattr(scope, field.name)) is not None
    ):
        _error("INVALID_SCHEMA", "pattern scope is invalid")
    if scope.mode is not None and scope.mode not in {"quantity_cost", "cost_only"}:
        _error("INVALID_SCHEMA", "pattern scope is invalid")
    _validate_recursive(scope)
    return scope


_PROPOSAL_TYPES: dict[CandidateKind, type[Proposal]] = {
    CandidateKind.SYNONYM_ABBREVIATION: SynonymAbbreviationProposal,
    CandidateKind.SLOT_TEMPLATE: SlotTemplateProposal,
    CandidateKind.INCLUDE_EXCLUDE: IncludeExcludeProposal,
    CandidateKind.SPLIT_MERGE: SplitMergeProposal,
    CandidateKind.CRITICAL_MODIFIER: CriticalModifierProposal,
    CandidateKind.MUST_LINK_CANNOT_LINK: MustLinkCannotLinkProposal,
    CandidateKind.CATEGORY_SPECIFIC_NORMALIZATION: CategorySpecificNormalizationProposal,
}


def _edit_one(left: str, right: str) -> bool:
    if min(len(left), len(right)) < 8 or abs(len(left) - len(right)) > 1:
        return False
    left_index = right_index = changes = 0
    while left_index < len(left) and right_index < len(right):
        if left[left_index] == right[right_index]:
            left_index += 1
            right_index += 1
            continue
        changes += 1
        if changes > 1:
            return False
        if len(left) > len(right):
            left_index += 1
        elif len(right) > len(left):
            right_index += 1
        else:
            left_index += 1
            right_index += 1
    return True


def _lexical_near(left: str, right: str) -> bool:
    if re.sub(r"[^\w]", "", left) == re.sub(r"[^\w]", "", right):
        return True
    left_parts, right_parts = left.split(), right.split()
    if len(left_parts) != len(right_parts):
        return False
    differences = [
        (left_part, right_part)
        for left_part, right_part in zip(left_parts, right_parts, strict=True)
        if left_part != right_part
    ]
    return len(differences) == 1 and (
        len(differences[0][0]) == 1 or len(differences[0][1]) == 1 or _edit_one(*differences[0])
    )


def _sorted_text_tuple(value: object, *, minimum: int) -> tuple[str, ...]:
    if (
        not isinstance(value, tuple)
        or len(value) < minimum
        or any(not isinstance(item, str) or not item for item in value)
        or value != tuple(sorted(set(value)))
    ):
        _error("INVALID_SCHEMA", "pattern template is invalid")
    return value


def _validate_template(template: object, kind: CandidateKind) -> Proposal:
    if not isinstance(kind, CandidateKind) or not isinstance(template, _PROPOSAL_TYPES[kind]):
        _error("INVALID_SCHEMA", "pattern template is invalid")
    _validate_recursive(template)
    if isinstance(template, SynonymAbbreviationProposal):
        variants = _sorted_text_tuple(template.variants, minimum=2)
        if len(variants) != 2 or not _lexical_near(*variants):
            _error("INVALID_SCHEMA", "pattern template is invalid")
    elif isinstance(template, SlotTemplateProposal):
        _sorted_text_tuple(template.slot_signatures, minimum=2)
        if not isinstance(template.skeleton, str) or not template.skeleton:
            _error("INVALID_SCHEMA", "pattern template is invalid")
    elif isinstance(template, IncludeExcludeProposal):
        if (
            not isinstance(template.predicate, str)
            or not template.predicate
            or template.polarity not in {"accept", "reject"}
        ):
            _error("INVALID_SCHEMA", "pattern template is invalid")
    elif isinstance(template, SplitMergeProposal):
        variants = _sorted_text_tuple(template.variants, minimum=2)
        if len(variants) != 2 or template.relation not in {
            "same_outcome",
            "partitioned_outcomes",
        }:
            _error("INVALID_SCHEMA", "pattern template is invalid")
    elif isinstance(template, CriticalModifierProposal):
        parts = template.modifier.split("|") if isinstance(template.modifier, str) else []
        if (
            len(parts) != 2
            or not all(parts)
            or parts[0] == parts[1]
            or template.disposition != "hard_boundary_review"
        ):
            _error("INVALID_SCHEMA", "pattern template is invalid")
    elif isinstance(template, MustLinkCannotLinkProposal):
        members = _sorted_text_tuple(template.members, minimum=2)
        if len(members) != 2 or template.relation not in {"must_link", "cannot_link"}:
            _error("INVALID_SCHEMA", "pattern template is invalid")
    elif (
        not isinstance(template.rewrite_from, str)
        or not template.rewrite_from
        or not isinstance(template.rewrite_to, str)
        or not template.rewrite_to
        or template.rewrite_from == template.rewrite_to
        or not isinstance(template.target_category, str)
        or not template.target_category
    ):
        _error("INVALID_SCHEMA", "pattern template is invalid")
    return template


def _proposal_outcome_is_consistent(proposal: Proposal, expected: OutcomeSignature | None) -> bool:
    if isinstance(proposal, IncludeExcludeProposal):
        return expected is not None and expected.action == proposal.polarity
    if isinstance(proposal, CriticalModifierProposal):
        return expected is None
    if isinstance(proposal, SplitMergeProposal):
        return (proposal.relation == "same_outcome") == (expected is not None)
    if isinstance(proposal, MustLinkCannotLinkProposal):
        return (proposal.relation == "must_link") == (expected is not None)
    if isinstance(proposal, CategorySpecificNormalizationProposal):
        return (
            expected is not None
            and expected.action == "accept"
            and expected.target_category == proposal.target_category
        )
    return expected is not None


def _validate_outcome(value: object, *, nullable: bool = False) -> OutcomeSignature | None:
    if value is None and nullable:
        return None
    if not isinstance(value, OutcomeSignature):
        _error("INVALID_SCHEMA", "outcome is invalid")
    if value.action not in {"accept", "reject"}:
        _error("INVALID_SCHEMA", "outcome is invalid")
    if value.action == "accept" and (
        not isinstance(value.mode, str)
        or value.mode not in {"quantity_cost", "cost_only"}
        or not isinstance(value.target_category, str)
        or not value.target_category
    ):
        _error("INVALID_SCHEMA", "outcome is invalid")
    if value.action == "reject" and (value.mode is not None or value.target_category is not None):
        _error("INVALID_SCHEMA", "outcome is invalid")
    _validate_recursive(value)
    return value


def _validate_support(value: object) -> SupportSummary:
    if not isinstance(value, SupportSummary):
        _error("INVALID_SCHEMA", "support is invalid")
    values = (
        value.support_atom_count,
        value.semantic_identity_count,
        value.document_set_count,
        value.confirmed_record_count,
        value.contradictory_atom_count,
    )
    if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in values):
        _error("INVALID_SCHEMA", "support is invalid")
    if (
        value.support_atom_count < 1
        or value.semantic_identity_count > value.support_atom_count
        or value.document_set_count > value.support_atom_count
        or value.confirmed_record_count < value.support_atom_count
    ):
        _error("INVARIANT_VIOLATION", "support is inconsistent")
    _sorted_hashes(value.support_refs, name="support references")
    if len(value.support_refs) > MAX_SUPPORT_REFS:
        _error("INVARIANT_VIOLATION", "support references exceed the public limit")
    return value


@dataclass(frozen=True, slots=True)
class PatternVersions:
    parser_version: str
    model_version: str
    taxonomy_version: str

    def __post_init__(self) -> None:
        _version(self.parser_version)
        _version(self.model_version)
        _version(self.taxonomy_version)


@dataclass(frozen=True, slots=True)
class OwnerApproval:
    owner_ref: str
    approval_ref: str
    approved_revision: int

    def __post_init__(self) -> None:
        _opaque_ref(self.owner_ref)
        _opaque_ref(self.approval_ref)
        _positive_int(self.approved_revision, name="approved revision")


@dataclass(frozen=True, slots=True)
class ReplayMetadata:
    replay_ref: str
    replay_fingerprint: str
    revision: int

    def __post_init__(self) -> None:
        _opaque_ref(self.replay_ref)
        _hash(self.replay_fingerprint)
        _positive_int(self.revision, name="replay revision")


@dataclass(frozen=True, slots=True)
class ActivationMetadata:
    activation_ref: str
    activation_fingerprint: str
    revision: int
    wave5_verification_ref: str

    def __post_init__(self) -> None:
        _opaque_ref(self.activation_ref)
        _hash(self.activation_fingerprint)
        _positive_int(self.revision, name="activation revision")
        _opaque_ref(self.wave5_verification_ref)


@dataclass(frozen=True, slots=True)
class RollbackMetadata:
    rollback_ref: str
    rollback_fingerprint: str
    source_revision: int

    def __post_init__(self) -> None:
        _opaque_ref(self.rollback_ref)
        _hash(self.rollback_fingerprint)
        _positive_int(self.source_revision, name="rollback source revision")


@dataclass(frozen=True, slots=True)
class PatternContradiction:
    contradiction_id: str
    relation: FeedbackRelation
    left_pattern_id: str
    right_pattern_id: str
    evidence_fingerprints: tuple[str, ...]

    def __post_init__(self) -> None:
        _hash(self.contradiction_id)
        if self.relation not in {FeedbackRelation.MUST_LINK, FeedbackRelation.CANNOT_LINK}:
            _error("INVALID_SCHEMA", "contradiction relation is invalid")
        _hash(self.left_pattern_id)
        _hash(self.right_pattern_id)
        if self.left_pattern_id >= self.right_pattern_id:
            _error("INVARIANT_VIOLATION", "contradiction endpoints are unordered")
        _sorted_hashes(self.evidence_fingerprints, name="contradiction evidence")


def pattern_record_fingerprint(value: object) -> str:
    if isinstance(value, PatternRecord):
        return _canonical_fingerprint(_material(value, exclude=frozenset({"fingerprint"})))
    return _canonical_fingerprint(value)


@dataclass(frozen=True, slots=True)
class PatternRecord:
    pattern_id: str
    candidate_id: str
    candidate_fingerprint: str
    candidate_kind: CandidateKind
    revision: int
    previous_fingerprint: str | None
    state: PatternState
    versions: PatternVersions
    scope: PatternScope
    template: Proposal
    expected_outcome: OutcomeSignature | None
    support: SupportSummary
    hard_negative_refs: tuple[str, ...]
    contradictions: tuple[PatternContradiction, ...]
    replay: ReplayMetadata | None
    owner: OwnerApproval | None
    activation: ActivationMetadata | None
    rollback: RollbackMetadata | None
    supersedes_pattern_id: str | None
    superseded_by_pattern_id: str | None
    risk_codes: tuple[str, ...]
    fingerprint: str
    version: str = PATTERN_REGISTRY_VERSION

    @property
    def proposal(self) -> Proposal:
        """Wave 3-compatible read alias; canonical material remains ``template``."""
        return self.template

    def __post_init__(self) -> None:
        _version(self.version, expected=PATTERN_REGISTRY_VERSION)
        _hash(self.pattern_id)
        _hash(self.candidate_id)
        _hash(self.candidate_fingerprint)
        if not isinstance(self.candidate_kind, CandidateKind):
            _error("CANDIDATE_IDENTITY_INVALID", "candidate kind is invalid")
        if self.pattern_id != self.candidate_id:
            _error("CANDIDATE_IDENTITY_INVALID", "pattern and candidate identity differ")
        _positive_int(self.revision, name="revision")
        previous = _hash(self.previous_fingerprint, nullable=True)
        if (self.revision == 1) != (previous is None):
            _error("REVISION_CHAIN_INVALID", "revision chain is invalid")
        if not isinstance(self.state, PatternState):
            _error("INVALID_SCHEMA", "pattern state is invalid")
        if not isinstance(self.versions, PatternVersions):
            _error("INVALID_SCHEMA", "pattern versions are invalid")
        scope = _validate_scope(self.scope)
        template = _validate_template(self.template, self.candidate_kind)
        expected_outcome = _validate_outcome(self.expected_outcome, nullable=True)
        support = _validate_support(self.support)
        _sorted_hashes(self.hard_negative_refs, name="hard negative references")
        if not isinstance(self.contradictions, tuple) or any(
            not isinstance(item, PatternContradiction) for item in self.contradictions
        ):
            _error("INVALID_SCHEMA", "contradictions are invalid")
        if self.contradictions != tuple(
            sorted(self.contradictions, key=lambda item: item.contradiction_id)
        ) or len({item.contradiction_id for item in self.contradictions}) != len(
            self.contradictions
        ):
            _error("INVARIANT_VIOLATION", "contradictions must be sorted and unique")
        for value, expected_type, name in (
            (self.replay, ReplayMetadata, "replay metadata"),
            (self.owner, OwnerApproval, "owner approval"),
            (self.activation, ActivationMetadata, "activation metadata"),
            (self.rollback, RollbackMetadata, "rollback metadata"),
        ):
            if value is not None and not isinstance(value, expected_type):
                _error("INVALID_SCHEMA", f"{name} is invalid")
        if self.replay is not None and self.replay.revision > self.revision:
            _error("STATE_METADATA_INVALID", "replay metadata revision is invalid")
        if self.owner is not None and self.owner.approved_revision > self.revision:
            _error("STATE_METADATA_INVALID", "owner approval revision is invalid")
        if self.activation is not None and self.activation.revision > self.revision:
            _error("STATE_METADATA_INVALID", "activation metadata revision is invalid")
        if self.rollback is not None and self.rollback.source_revision >= self.revision:
            _error("STATE_METADATA_INVALID", "rollback metadata is invalid")
        supersedes = _hash(self.supersedes_pattern_id, nullable=True)
        superseded_by = _hash(self.superseded_by_pattern_id, nullable=True)
        if supersedes == self.pattern_id or superseded_by == self.pattern_id:
            _error("INVARIANT_VIOLATION", "supersession identity is invalid")
        _sorted_risks(self.risk_codes)
        candidate_id = _canonical_fingerprint(
            {
                "version": PATTERN_CANDIDATE_VERSION,
                "kind": self.candidate_kind.value,
                "scope": scope,
                "proposal": template,
            }
        )
        candidate_fingerprint = _canonical_fingerprint(
            {
                "candidate_id": candidate_id,
                "support": support,
                "risks": self.risk_codes,
            }
        )
        if (
            self.candidate_id != candidate_id
            or self.pattern_id != candidate_id
            or self.candidate_fingerprint != candidate_fingerprint
            or not _proposal_outcome_is_consistent(template, expected_outcome)
        ):
            _error("CANDIDATE_IDENTITY_INVALID", "candidate identity is invalid")
        if self.state is PatternState.PROPOSED and any(
            item is not None for item in (self.owner, self.activation, self.rollback)
        ):
            _error("STATE_METADATA_INVALID", "proposed metadata is invalid")
        if self.state is PatternState.SHADOW and any(
            item is not None for item in (self.owner, self.activation, self.rollback)
        ):
            _error("STATE_METADATA_INVALID", "shadow metadata is invalid")
        if self.state is PatternState.OWNER_APPROVED and (
            self.owner is None or self.activation is not None or self.rollback is not None
        ):
            _error("STATE_METADATA_INVALID", "owner approval metadata is invalid")
        if (
            self.state is PatternState.OWNER_APPROVED
            and self.owner is not None
            and self.owner.approved_revision != self.revision
        ):
            _error("STATE_METADATA_INVALID", "owner approval revision is invalid")
        if self.state is PatternState.ACTIVE and (
            self.owner is None or self.activation is None or self.rollback is not None
        ):
            _error("STATE_METADATA_INVALID", "active metadata is invalid")
        if self.state is PatternState.ACTIVE and (
            self.owner is None
            or self.activation is None
            or self.owner.approved_revision >= self.revision
            or self.activation.revision != self.revision
        ):
            _error("STATE_METADATA_INVALID", "imported active metadata is invalid")
        if self.state is PatternState.SUSPENDED and (
            self.rollback is None and not self.contradictions
        ):
            _error("STATE_METADATA_INVALID", "suspension metadata is invalid")
        if self.state is PatternState.SUSPENDED and (
            (self.owner is None) != (self.activation is None)
        ):
            _error("STATE_METADATA_INVALID", "suspension provenance is incomplete")
        if self.state in {PatternState.SUSPENDED, PatternState.RETIRED} and (
            (self.owner is not None and self.owner.approved_revision >= self.revision)
            or (self.activation is not None and self.activation.revision >= self.revision)
        ):
            _error("STATE_METADATA_INVALID", "retained lifecycle provenance is invalid")
        if self.activation is not None and self.owner is None:
            _error("STATE_METADATA_INVALID", "activation provenance requires owner approval")
        if self.superseded_by_pattern_id is not None and self.state is not PatternState.RETIRED:
            _error("STATE_METADATA_INVALID", "superseded pattern must be retired")
        supplied = _hash(self.fingerprint)
        if supplied != pattern_record_fingerprint(self):
            _error("FINGERPRINT_MISMATCH", "pattern fingerprint does not match")


@dataclass(frozen=True, slots=True)
class FeedbackConfirmation:
    confirmation_ref: str
    document_set_ref: str
    apply_fingerprint: str
    result_fingerprint: str
    outcome: OutcomeSignature

    def __post_init__(self) -> None:
        _opaque_ref(self.confirmation_ref)
        _opaque_ref(self.document_set_ref)
        _hash(self.apply_fingerprint)
        _hash(self.result_fingerprint)
        _validate_outcome(self.outcome)


@dataclass(frozen=True, slots=True)
class FeedbackEndpoint:
    pattern_id: str
    candidate_id: str
    outcome: OutcomeSignature

    def __post_init__(self) -> None:
        _hash(self.pattern_id)
        _hash(self.candidate_id)
        if self.pattern_id != self.candidate_id:
            _error("CANDIDATE_IDENTITY_INVALID", "feedback endpoint identity is invalid")
        _validate_outcome(self.outcome)


@dataclass(frozen=True, slots=True)
class FeedbackProvenance:
    confirmations: tuple[FeedbackConfirmation, ...]
    document_set_refs: tuple[str, ...]
    apply_fingerprints: tuple[str, ...]
    result_fingerprints: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.confirmations, tuple)
            or len(self.confirmations) != 2
            or any(not isinstance(item, FeedbackConfirmation) for item in self.confirmations)
        ):
            _error("INSUFFICIENT_CONFIRMATION", "two authoritative confirmations are required")
        if (
            self.confirmations
            != tuple(sorted(self.confirmations, key=lambda item: item.confirmation_ref))
            or len({item.confirmation_ref for item in self.confirmations}) != 2
        ):
            _error("INVARIANT_VIOLATION", "confirmation records are invalid")
        refs = _sorted_hashes(self.document_set_refs, name="document set references")
        applies = _sorted_hashes(self.apply_fingerprints, name="apply fingerprints")
        results = _sorted_hashes(self.result_fingerprints, name="result fingerprints")
        if len(refs) != 2 or len(applies) != 2 or len(results) != 2:
            _error("INSUFFICIENT_CONFIRMATION", "independent confirmation provenance is required")
        if (
            refs != tuple(sorted(item.document_set_ref for item in self.confirmations))
            or applies != tuple(sorted(item.apply_fingerprint for item in self.confirmations))
            or results != tuple(sorted(item.result_fingerprint for item in self.confirmations))
        ):
            _error("PROVENANCE_MISMATCH", "confirmation provenance does not match")


def feedback_edge_fingerprint(value: object) -> str:
    if isinstance(value, FeedbackEdge):
        return _canonical_fingerprint(_material(value, exclude=frozenset({"fingerprint"})))
    return _canonical_fingerprint(value)


@dataclass(frozen=True, slots=True)
class FeedbackEdge:
    edge_id: str
    relation: FeedbackRelation
    direction: FeedbackDirection
    reason: FeedbackReason
    source: FeedbackEndpoint
    target: FeedbackEndpoint
    provenance: FeedbackProvenance
    contradiction_ids: tuple[str, ...]
    fingerprint: str
    version: str = FEEDBACK_GRAPH_VERSION

    def __post_init__(self) -> None:
        _version(self.version, expected=FEEDBACK_GRAPH_VERSION)
        _hash(self.edge_id)
        if not isinstance(self.relation, FeedbackRelation):
            _error("INVALID_SCHEMA", "feedback edge is invalid")
        if not isinstance(self.direction, FeedbackDirection) or not isinstance(
            self.reason, FeedbackReason
        ):
            _error("INVALID_SCHEMA", "feedback direction or reason is invalid")
        if not isinstance(self.source, FeedbackEndpoint) or not isinstance(
            self.target, FeedbackEndpoint
        ):
            _error("INVALID_SCHEMA", "feedback endpoints are invalid")
        if self.source.pattern_id == self.target.pattern_id:
            _error("INVARIANT_VIOLATION", "feedback edge cannot be self-referential")
        if not isinstance(self.provenance, FeedbackProvenance):
            _error("INVALID_SCHEMA", "feedback provenance is invalid")
        _sorted_hashes(self.contradiction_ids, name="contradiction identifiers")
        if self.relation is FeedbackRelation.HARD_NEGATIVE:
            if self.direction is not FeedbackDirection.DIRECTIONAL:
                _error("DIRECTION_INVALID", "hard negative must be directional")
        elif self.direction is not FeedbackDirection.SYMMETRIC:
            _error("DIRECTION_INVALID", "link relation must be symmetric")
        elif self.source.pattern_id >= self.target.pattern_id:
            _error("INVARIANT_VIOLATION", "symmetric endpoints are unordered")
        endpoint_outcomes = tuple(
            sorted(
                (
                    canonical_json_bytes(self.source.outcome),
                    canonical_json_bytes(self.target.outcome),
                )
            )
        )
        confirmation_outcomes = tuple(
            sorted(canonical_json_bytes(item.outcome) for item in self.provenance.confirmations)
        )
        if confirmation_outcomes != endpoint_outcomes:
            _error("PROVENANCE_MISMATCH", "confirmations are not bound to edge endpoints")
        if self.relation is FeedbackRelation.MUST_LINK:
            if (
                self.reason is not FeedbackReason.EXPLICIT_AUTHORITATIVE_CONFIRMATION
                or self.source.outcome != self.target.outcome
            ):
                _error("OUTCOME_CONFLICT", "must-link requires one equal authoritative outcome")
        elif (
            self.reason is not FeedbackReason.EXPLICIT_AUTHORITATIVE_CONFLICT
            or self.source.outcome == self.target.outcome
        ):
            _error("OUTCOME_CONFLICT", "negative relation requires a confirmed outcome conflict")
        identity = _canonical_fingerprint(
            {
                "version": self.version,
                "relation": self.relation.value,
                "direction": self.direction.value,
                "reason": self.reason.value,
                "source": self.source,
                "target": self.target,
                "provenance": self.provenance,
            }
        )
        if self.edge_id != identity:
            _error("FINGERPRINT_MISMATCH", "feedback edge identity does not match")
        if _hash(self.fingerprint) != feedback_edge_fingerprint(self):
            _error("FINGERPRINT_MISMATCH", "feedback edge fingerprint does not match")


def event_fingerprint(value: object) -> str:
    """Canonical fingerprint for event material and public deterministic payloads."""
    if isinstance(value, PatternRegistryEvent):
        return _canonical_fingerprint(_material(value, exclude=frozenset({"fingerprint"})))
    return _canonical_fingerprint(value)


@dataclass(frozen=True, slots=True)
class PatternRegistryEvent:
    event_id: str
    event_type: PatternRegistryEventType
    pattern_id: str
    revision: int
    previous_event_fingerprint: str | None
    payload_fingerprint: str
    actor_ref: str
    fingerprint: str
    version: str = PATTERN_REGISTRY_EVENT_VERSION

    def __post_init__(self) -> None:
        _version(self.version, expected=PATTERN_REGISTRY_EVENT_VERSION)
        _hash(self.event_id)
        if not isinstance(self.event_type, PatternRegistryEventType):
            _error("INVALID_SCHEMA", "event type is invalid")
        _hash(self.pattern_id)
        revision = _positive_int(self.revision, name="event revision")
        previous = _hash(self.previous_event_fingerprint, nullable=True)
        if (revision == 1) != (previous is None):
            _error("EVENT_CHAIN_INVALID", "event chain is invalid")
        _hash(self.payload_fingerprint)
        _opaque_ref(self.actor_ref)
        if _hash(self.fingerprint) != event_fingerprint(self):
            _error("FINGERPRINT_MISMATCH", "event fingerprint does not match")


def hard_negative_index_fingerprint(value: object) -> str:
    if isinstance(value, HardNegativeIndex):
        return _canonical_fingerprint(_material(value, exclude=frozenset({"fingerprint"})))
    return _canonical_fingerprint(value)


@dataclass(frozen=True, slots=True)
class HardNegativeIndexEntry:
    source_pattern_id: str
    target_pattern_id: str
    edge_fingerprint: str

    def __post_init__(self) -> None:
        _hash(self.source_pattern_id)
        _hash(self.target_pattern_id)
        _hash(self.edge_fingerprint)
        if self.source_pattern_id == self.target_pattern_id:
            _error("INVARIANT_VIOLATION", "hard negative cannot be self-referential")


@dataclass(frozen=True, slots=True)
class HardNegativeIndex:
    entries: tuple[HardNegativeIndexEntry, ...]
    fingerprint: str
    version: str = FEEDBACK_GRAPH_HARD_NEGATIVE_VERSION

    def __post_init__(self) -> None:
        _version(self.version, expected=FEEDBACK_GRAPH_HARD_NEGATIVE_VERSION)
        if not isinstance(self.entries, tuple) or any(
            not isinstance(item, HardNegativeIndexEntry) for item in self.entries
        ):
            _error("INVALID_SCHEMA", "hard negative entries are invalid")
        ordered = tuple(
            sorted(
                self.entries,
                key=lambda item: (
                    item.source_pattern_id,
                    item.target_pattern_id,
                    item.edge_fingerprint,
                ),
            )
        )
        if self.entries != ordered or len(set(self.entries)) != len(self.entries):
            _error("INVARIANT_VIOLATION", "hard negative entries must be sorted and unique")
        if _hash(self.fingerprint) != hard_negative_index_fingerprint(self):
            _error("FINGERPRINT_MISMATCH", "hard negative index fingerprint does not match")


@dataclass(frozen=True, slots=True)
class PatternIntegrityReport:
    pattern_id: str
    checked_revision: int
    record_fingerprint: str
    event_fingerprints: tuple[str, ...]
    edge_fingerprints: tuple[str, ...]
    contradiction_ids: tuple[str, ...]
    valid: bool
    issues: tuple[str, ...]
    version: str = PATTERN_REGISTRY_VERSION

    def __post_init__(self) -> None:
        _version(self.version, expected=PATTERN_REGISTRY_VERSION)
        _hash(self.pattern_id)
        _positive_int(self.checked_revision, name="checked revision")
        _hash(self.record_fingerprint)
        _sorted_hashes(self.event_fingerprints, name="event fingerprints")
        _sorted_hashes(self.edge_fingerprints, name="edge fingerprints")
        _sorted_hashes(self.contradiction_ids, name="contradiction identifiers")
        if not isinstance(self.valid, bool):
            _error("INVALID_SCHEMA", "integrity state is invalid")
        if (
            not isinstance(self.issues, tuple)
            or any(not isinstance(item, str) or not _RISK.fullmatch(item) for item in self.issues)
            or self.issues != tuple(sorted(set(self.issues)))
        ):
            _error("INVALID_SCHEMA", "integrity issues are invalid")
        if self.valid != (not self.issues):
            _error("INVARIANT_VIOLATION", "integrity state and issues differ")


def validate_state_transition(from_state: PatternState, to_state: PatternState) -> None:
    """Reject Wave 4 activation while preserving future verified import support."""
    if not isinstance(from_state, PatternState) or not isinstance(to_state, PatternState):
        _error("STATE_TRANSITION_INVALID", "state transition is invalid")
    if from_state is PatternState.OWNER_APPROVED and to_state is PatternState.ACTIVE:
        _error("WAVE5_REQUIRED", "activation requires Wave 5")
    allowed = {
        (PatternState.PROPOSED, PatternState.SHADOW),
        (PatternState.SHADOW, PatternState.OWNER_APPROVED),
        (PatternState.PROPOSED, PatternState.RETIRED),
        (PatternState.SHADOW, PatternState.RETIRED),
        (PatternState.OWNER_APPROVED, PatternState.RETIRED),
        (PatternState.ACTIVE, PatternState.SUSPENDED),
        (PatternState.ACTIVE, PatternState.RETIRED),
        (PatternState.SUSPENDED, PatternState.RETIRED),
    }
    if (from_state, to_state) not in allowed:
        _error("STATE_TRANSITION_INVALID", "state transition is invalid")


def create_pattern_record(**values: object) -> PatternRecord:
    """Create a validated record with a canonical fingerprint supplied by this module."""
    names = {field.name for field in fields(PatternRecord)}
    if "fingerprint" in values or set(values) - (names - {"fingerprint"}):
        _error("INVALID_SCHEMA", "pattern record constructor input is invalid")
    payload = {**values, "version": values.get("version", PATTERN_REGISTRY_VERSION)}
    required = names - {"fingerprint"}
    if set(payload) != required:
        _error("INVALID_SCHEMA", "pattern record constructor input is invalid")
    try:
        return PatternRecord(**payload, fingerprint=pattern_record_fingerprint(payload))
    except PatternRegistryError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise PatternRegistryError("INVALID_SCHEMA", "pattern record input is invalid") from exc


def create_feedback_edge(**values: object) -> FeedbackEdge:
    """Create a validated graph edge with deterministic edge and record fingerprints."""
    names = {field.name for field in fields(FeedbackEdge)}
    forbidden = {"edge_id", "fingerprint"}
    if forbidden & set(values) or set(values) - (names - forbidden):
        _error("INVALID_SCHEMA", "feedback edge constructor input is invalid")
    payload = {**values, "version": values.get("version", FEEDBACK_GRAPH_VERSION)}
    required = names - forbidden
    if set(payload) != required:
        _error("INVALID_SCHEMA", "feedback edge constructor input is invalid")
    try:
        relation = payload["relation"]
        direction = payload["direction"]
        reason = payload["reason"]
        source = payload["source"]
        target = payload["target"]
        provenance = payload["provenance"]
        if not isinstance(relation, FeedbackRelation):
            _error("INVALID_SCHEMA", "feedback relation is invalid")
        if not isinstance(direction, FeedbackDirection):
            _error("INVALID_SCHEMA", "feedback direction is invalid")
        if not isinstance(reason, FeedbackReason):
            _error("INVALID_SCHEMA", "feedback reason is invalid")
        if not isinstance(source, FeedbackEndpoint) or not isinstance(target, FeedbackEndpoint):
            _error("INVALID_SCHEMA", "feedback endpoints are invalid")
        if not isinstance(provenance, FeedbackProvenance):
            _error("INVALID_SCHEMA", "feedback provenance is invalid")
        edge_id = _canonical_fingerprint(
            {
                "version": payload["version"],
                "relation": relation.value,
                "direction": direction.value,
                "reason": reason.value,
                "source": source,
                "target": target,
                "provenance": provenance,
            }
        )
        material = {"edge_id": edge_id, **payload}
        return FeedbackEdge(**material, fingerprint=feedback_edge_fingerprint(material))
    except PatternRegistryError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise PatternRegistryError("INVALID_SCHEMA", "feedback edge input is invalid") from exc


def create_pattern_registry_event(**values: object) -> PatternRegistryEvent:
    """Create a deterministic immutable registry event."""
    names = {field.name for field in fields(PatternRegistryEvent)}
    if "fingerprint" in values or set(values) - (names - {"fingerprint"}):
        _error("INVALID_SCHEMA", "registry event constructor input is invalid")
    payload = {**values, "version": values.get("version", PATTERN_REGISTRY_EVENT_VERSION)}
    required = names - {"fingerprint"}
    if set(payload) != required:
        _error("INVALID_SCHEMA", "registry event constructor input is invalid")
    return PatternRegistryEvent(**payload, fingerprint=event_fingerprint(payload))


def create_hard_negative_index(**values: object) -> HardNegativeIndex:
    """Create logical hard-negative metadata without vector or term material."""
    names = {field.name for field in fields(HardNegativeIndex)}
    if "fingerprint" in values or set(values) - (names - {"fingerprint"}):
        _error("INVALID_SCHEMA", "hard negative constructor input is invalid")
    payload = {**values, "version": values.get("version", FEEDBACK_GRAPH_HARD_NEGATIVE_VERSION)}
    required = names - {"fingerprint"}
    if set(payload) != required:
        _error("INVALID_SCHEMA", "hard negative constructor input is invalid")
    return HardNegativeIndex(**payload, fingerprint=hard_negative_index_fingerprint(payload))


def _mapping(value: object, names: set[str], *, model: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != names:
        _error("INVALID_SCHEMA", f"{model} payload is invalid")
    return value


def _enum(enum: type[StrEnum], value: object, *, name: str) -> StrEnum:
    if not isinstance(value, str):
        _error("INVALID_SCHEMA", f"{name} is invalid")
    try:
        return enum(value)
    except ValueError as exc:
        raise PatternRegistryError("INVALID_SCHEMA", f"{name} is invalid") from exc


def _outcome_from_mapping(value: object, *, nullable: bool = False) -> OutcomeSignature | None:
    if value is None and nullable:
        return None
    raw = _mapping(value, {"action", "mode", "target_category"}, model="outcome")
    return _validate_outcome(OutcomeSignature(raw["action"], raw["mode"], raw["target_category"]))


def _scope_from_mapping(value: object) -> PatternScope:
    raw = _mapping(value, set(PatternScope.__dataclass_fields__), model="scope")
    try:
        return _validate_scope(PatternScope(**raw))
    except (TypeError, ValueError) as exc:
        raise PatternRegistryError("INVALID_SCHEMA", "scope payload is invalid") from exc


def _support_from_mapping(value: object) -> SupportSummary:
    raw = _mapping(value, set(SupportSummary.__dataclass_fields__), model="support")
    refs = raw.get("support_refs")
    if not isinstance(refs, (list, tuple)):
        _error("INVALID_SCHEMA", "support payload is invalid")
    try:
        return _validate_support(SupportSummary(**{**raw, "support_refs": tuple(refs)}))
    except (TypeError, ValueError) as exc:
        raise PatternRegistryError("INVALID_SCHEMA", "support payload is invalid") from exc


def _json_array(value: object, *, name: str) -> list[object]:
    if not isinstance(value, list):
        _error("INVALID_SCHEMA", f"{name} must be a JSON array")
    return value


def _template_from_mapping(value: object, kind: CandidateKind) -> Proposal:
    if not isinstance(value, Mapping):
        _error("INVALID_SCHEMA", "template payload is invalid")
    raw = dict(value)
    try:
        if set(raw) == {"variants"}:
            return _validate_template(
                SynonymAbbreviationProposal(
                    tuple(_json_array(raw["variants"], name="synonym variants"))
                ),
                kind,
            )
        if set(raw) == {"skeleton", "slot_signatures"}:
            return _validate_template(
                SlotTemplateProposal(
                    raw["skeleton"],
                    tuple(_json_array(raw["slot_signatures"], name="slot signatures")),
                ),
                kind,
            )
        if set(raw) == {"predicate", "polarity"}:
            return _validate_template(
                IncludeExcludeProposal(raw["predicate"], raw["polarity"]), kind
            )
        if set(raw) == {"variants", "relation"}:
            return _validate_template(
                SplitMergeProposal(
                    tuple(_json_array(raw["variants"], name="split/merge variants")),
                    raw["relation"],
                ),
                kind,
            )
        if set(raw) == {"modifier", "disposition"}:
            return _validate_template(
                CriticalModifierProposal(raw["modifier"], raw["disposition"]), kind
            )
        if set(raw) == {"relation", "members"}:
            return _validate_template(
                MustLinkCannotLinkProposal(
                    raw["relation"],
                    tuple(_json_array(raw["members"], name="link members")),
                ),
                kind,
            )
        if set(raw) == {"rewrite_from", "rewrite_to", "target_category"}:
            return _validate_template(
                CategorySpecificNormalizationProposal(
                    raw["rewrite_from"], raw["rewrite_to"], raw["target_category"]
                ),
                kind,
            )
    except (TypeError, ValueError) as exc:
        raise PatternRegistryError("INVALID_SCHEMA", "template payload is invalid") from exc
    _error("INVALID_SCHEMA", "template payload is invalid")


def _owner_from_mapping(value: object) -> OwnerApproval | None:
    if value is None:
        return None
    raw = _mapping(value, set(OwnerApproval.__dataclass_fields__), model="owner approval")
    return OwnerApproval(**raw)


def _replay_from_mapping(value: object) -> ReplayMetadata | None:
    if value is None:
        return None
    raw = _mapping(value, set(ReplayMetadata.__dataclass_fields__), model="replay metadata")
    return ReplayMetadata(**raw)


def _activation_from_mapping(value: object) -> ActivationMetadata | None:
    if value is None:
        return None
    raw = _mapping(value, set(ActivationMetadata.__dataclass_fields__), model="activation metadata")
    return ActivationMetadata(**raw)


def _rollback_from_mapping(value: object) -> RollbackMetadata | None:
    if value is None:
        return None
    raw = _mapping(value, set(RollbackMetadata.__dataclass_fields__), model="rollback metadata")
    return RollbackMetadata(**raw)


def _contradiction_from_mapping(value: object) -> PatternContradiction:
    raw = _mapping(value, set(PatternContradiction.__dataclass_fields__), model="contradiction")
    evidence = raw["evidence_fingerprints"]
    if not isinstance(evidence, (list, tuple)):
        _error("INVALID_SCHEMA", "contradiction payload is invalid")
    return PatternContradiction(
        contradiction_id=raw["contradiction_id"],
        relation=_enum(FeedbackRelation, raw["relation"], name="contradiction relation"),
        left_pattern_id=raw["left_pattern_id"],
        right_pattern_id=raw["right_pattern_id"],
        evidence_fingerprints=tuple(evidence),
    )


def _tuple(value: object, *, name: str) -> tuple[object, ...]:
    if not isinstance(value, (list, tuple)):
        _error("INVALID_SCHEMA", f"{name} is invalid")
    return tuple(value)


def canonical_payload_bytes(model: object) -> bytes:
    """Canonical bytes for persistence; the returned value contains no mutable graph."""
    _validate_recursive(model)
    try:
        return canonical_json_bytes(_plain(model))
    except Exception as exc:
        raise PatternRegistryError("INVARIANT_VIOLATION", "canonical payload is invalid") from exc


def load_pattern_record(value: object) -> PatternRecord:
    """Strictly load a canonical record mapping from the private store."""
    names = {field.name for field in fields(PatternRecord)}
    raw = _mapping(value, names, model="pattern record")
    try:
        candidate_kind = _enum(CandidateKind, raw["candidate_kind"], name="candidate kind")
        versions = PatternVersions(
            **_mapping(raw["versions"], set(PatternVersions.__dataclass_fields__), model="versions")
        )
        return PatternRecord(
            pattern_id=raw["pattern_id"],
            candidate_id=raw["candidate_id"],
            candidate_fingerprint=raw["candidate_fingerprint"],
            candidate_kind=candidate_kind,
            revision=raw["revision"],
            previous_fingerprint=raw["previous_fingerprint"],
            state=_enum(PatternState, raw["state"], name="pattern state"),
            versions=versions,
            scope=_scope_from_mapping(raw["scope"]),
            template=_template_from_mapping(raw["template"], candidate_kind),
            expected_outcome=_outcome_from_mapping(raw["expected_outcome"], nullable=True),
            support=_support_from_mapping(raw["support"]),
            hard_negative_refs=_tuple(raw["hard_negative_refs"], name="hard negative references"),
            contradictions=tuple(
                _contradiction_from_mapping(item)
                for item in _tuple(raw["contradictions"], name="contradictions")
            ),
            replay=_replay_from_mapping(raw["replay"]),
            owner=_owner_from_mapping(raw["owner"]),
            activation=_activation_from_mapping(raw["activation"]),
            rollback=_rollback_from_mapping(raw["rollback"]),
            supersedes_pattern_id=raw["supersedes_pattern_id"],
            superseded_by_pattern_id=raw["superseded_by_pattern_id"],
            risk_codes=_tuple(raw["risk_codes"], name="risk codes"),
            fingerprint=raw["fingerprint"],
            version=raw["version"],
        )
    except (TypeError, ValueError, PatternRegistryError) as exc:
        if isinstance(exc, PatternRegistryError):
            raise
        raise PatternRegistryError("INVALID_SCHEMA", "pattern record payload is invalid") from exc


def load_feedback_edge(value: object) -> FeedbackEdge:
    """Strictly load a feedback edge and its independent confirmations."""
    try:
        raw = _mapping(value, {field.name for field in fields(FeedbackEdge)}, model="feedback edge")
        provenance_raw = _mapping(
            raw["provenance"],
            set(FeedbackProvenance.__dataclass_fields__),
            model="feedback provenance",
        )
        confirmations = []
        for item in _tuple(provenance_raw["confirmations"], name="confirmations"):
            confirmation = _mapping(
                item, set(FeedbackConfirmation.__dataclass_fields__), model="confirmation"
            )
            confirmations.append(
                FeedbackConfirmation(
                    confirmation_ref=confirmation["confirmation_ref"],
                    document_set_ref=confirmation["document_set_ref"],
                    apply_fingerprint=confirmation["apply_fingerprint"],
                    result_fingerprint=confirmation["result_fingerprint"],
                    outcome=_outcome_from_mapping(confirmation["outcome"]),
                )
            )
        provenance = FeedbackProvenance(
            confirmations=tuple(confirmations),
            document_set_refs=_tuple(
                provenance_raw["document_set_refs"], name="document set references"
            ),
            apply_fingerprints=_tuple(
                provenance_raw["apply_fingerprints"], name="apply fingerprints"
            ),
            result_fingerprints=_tuple(
                provenance_raw["result_fingerprints"], name="result fingerprints"
            ),
        )
        source_raw = _mapping(
            raw["source"], set(FeedbackEndpoint.__dataclass_fields__), model="source endpoint"
        )
        target_raw = _mapping(
            raw["target"], set(FeedbackEndpoint.__dataclass_fields__), model="target endpoint"
        )
        return FeedbackEdge(
            edge_id=raw["edge_id"],
            relation=_enum(FeedbackRelation, raw["relation"], name="feedback relation"),
            direction=_enum(FeedbackDirection, raw["direction"], name="feedback direction"),
            reason=_enum(FeedbackReason, raw["reason"], name="feedback reason"),
            source=FeedbackEndpoint(
                pattern_id=source_raw["pattern_id"],
                candidate_id=source_raw["candidate_id"],
                outcome=_outcome_from_mapping(source_raw["outcome"]),
            ),
            target=FeedbackEndpoint(
                pattern_id=target_raw["pattern_id"],
                candidate_id=target_raw["candidate_id"],
                outcome=_outcome_from_mapping(target_raw["outcome"]),
            ),
            provenance=provenance,
            contradiction_ids=_tuple(raw["contradiction_ids"], name="contradiction identifiers"),
            fingerprint=raw["fingerprint"],
            version=raw["version"],
        )
    except PatternRegistryError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise PatternRegistryError("INVALID_SCHEMA", "feedback edge payload is invalid") from exc


def load_pattern_registry_event(value: object) -> PatternRegistryEvent:
    """Strictly load one append-only event."""
    raw = _mapping(
        value, {field.name for field in fields(PatternRegistryEvent)}, model="registry event"
    )
    return PatternRegistryEvent(
        event_id=raw["event_id"],
        event_type=_enum(PatternRegistryEventType, raw["event_type"], name="event type"),
        pattern_id=raw["pattern_id"],
        revision=raw["revision"],
        previous_event_fingerprint=raw["previous_event_fingerprint"],
        payload_fingerprint=raw["payload_fingerprint"],
        actor_ref=raw["actor_ref"],
        fingerprint=raw["fingerprint"],
        version=raw["version"],
    )


def load_hard_negative_index(value: object) -> HardNegativeIndex:
    """Strictly load logical hard-negative metadata, never vector content."""
    raw = _mapping(
        value, {field.name for field in fields(HardNegativeIndex)}, model="hard negative index"
    )
    try:
        entries = tuple(
            HardNegativeIndexEntry(
                **_mapping(
                    item,
                    set(HardNegativeIndexEntry.__dataclass_fields__),
                    model="hard negative entry",
                )
            )
            for item in _tuple(raw["entries"], name="hard negative entries")
        )
        return HardNegativeIndex(
            entries=entries,
            fingerprint=raw["fingerprint"],
            version=raw["version"],
        )
    except PatternRegistryError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise PatternRegistryError("INVALID_SCHEMA", "hard negative payload is invalid") from exc


def load_integrity_report(value: object) -> PatternIntegrityReport:
    """Strictly load a deterministic integrity report."""
    raw = _mapping(
        value, {field.name for field in fields(PatternIntegrityReport)}, model="integrity report"
    )
    return PatternIntegrityReport(
        pattern_id=raw["pattern_id"],
        checked_revision=raw["checked_revision"],
        record_fingerprint=raw["record_fingerprint"],
        event_fingerprints=_tuple(raw["event_fingerprints"], name="event fingerprints"),
        edge_fingerprints=_tuple(raw["edge_fingerprints"], name="edge fingerprints"),
        contradiction_ids=_tuple(raw["contradiction_ids"], name="contradiction identifiers"),
        valid=raw["valid"],
        issues=_tuple(raw["issues"], name="integrity issues"),
        version=raw["version"],
    )
