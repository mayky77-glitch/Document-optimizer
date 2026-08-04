"""Pure, private HybridRetrieval-1.0 contract; adapters are deliberately separate."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, fields, is_dataclass
from enum import StrEnum
from functools import cmp_to_key
from math import gcd
from typing import Any

from .offline import OutcomeSignature
from .pattern_models import PatternState, PatternVersions
from .pattern_registry import (
    DecisionSource,
    PatternDecision,
    RegistryHistory,
    resolve_history_precedence,
)

HYBRID_RETRIEVAL_VERSION = "HybridRetrieval-1.0"
RRF_K = 60
SCORE_SCALE = 1_000_000
MAX_LIMIT = 100
MAX_EVIDENCE = MAX_HARD_NEGATIVES = 4096
MAX_SIGNALS = 1000
MAX_REFS = 128
MAX_CODES = 64

_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_TOKEN = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")


class HybridRetrievalError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__("hybrid retrieval input is invalid")
        self.code = code


class HybridStatus(StrEnum):
    AUTHORITATIVE_EXACT = "authoritative_exact"
    AUTHORITATIVE_PATTERN = "authoritative_pattern"
    REVIEW_REQUIRED = "review_required"
    UNAVAILABLE = "unavailable"


class EvidenceKind(StrEnum):
    CONFIRMED_EXAMPLE = "confirmed_example"
    ACTIVE_PATTERN_PROTOTYPE = "active_pattern_prototype"


class RepresentationKind(StrEnum):
    FULL_TERM = "full_term"
    SEMANTIC_SKELETON = "semantic_skeleton"


class RetrievalChannel(StrEnum):
    PATTERN_MASK = "pattern_mask"
    LEXICAL = "lexical"
    DENSE_FULL_TERM = "dense_full_term"
    DENSE_SEMANTIC_SKELETON = "dense_semantic_skeleton"
    PROTOTYPE_FULL_TERM = "prototype_full_term"
    PROTOTYPE_SEMANTIC_SKELETON = "prototype_semantic_skeleton"


class ReasonCode(StrEnum):
    EXACT_FEEDBACK_APPLIED = "exact_feedback_applied"
    ACTIVE_PATTERN_APPLIED = "active_pattern_applied"
    PATTERN_CONFLICT = "pattern_conflict"
    PATTERN_MASK_MATCH = "pattern_mask_match"
    LEXICAL_MATCH = "lexical_match"
    DENSE_FULL_TERM_MATCH = "dense_full_term_match"
    DENSE_SEMANTIC_SKELETON_MATCH = "dense_semantic_skeleton_match"
    PROTOTYPE_FULL_TERM_MATCH = "prototype_full_term_match"
    PROTOTYPE_SEMANTIC_SKELETON_MATCH = "prototype_semantic_skeleton_match"
    SLOT_MATCH = "slot_match"
    HARD_NEGATIVE_NEARER_OR_EQUAL = "hard_negative_nearer_or_equal"
    FORBIDDEN_HARD_NEGATIVE = "forbidden_hard_negative"
    EXACT_ONLY = "exact_only"
    SOURCE_UNAVAILABLE = "source_unavailable"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


@dataclass(frozen=True, slots=True)
class HybridQuery:
    query_ref: str
    tenant_ref: str
    project_ref: str | None
    document_type_fingerprint: str
    taxonomy_version_fingerprint: str
    scope_fingerprint: str
    consequential_version_fingerprint: str
    embedding_identity_fingerprint: str
    confirmed_source_identity_fingerprint: str
    prototype_source_identity_fingerprint: str
    hard_negative_identity_fingerprint: str
    full_term_fingerprint: str
    skeleton_fingerprint: str
    exact_only: bool
    limit: int
    fingerprint: str
    version: str = HYBRID_RETRIEVAL_VERSION

    def __post_init__(self) -> None:
        _refs(
            self.query_ref,
            self.tenant_ref,
            self.project_ref,
            self.document_type_fingerprint,
            self.taxonomy_version_fingerprint,
            self.scope_fingerprint,
            self.consequential_version_fingerprint,
            self.embedding_identity_fingerprint,
            self.confirmed_source_identity_fingerprint,
            self.prototype_source_identity_fingerprint,
            self.hard_negative_identity_fingerprint,
            self.full_term_fingerprint,
            self.skeleton_fingerprint,
        )
        if (
            not isinstance(self.exact_only, bool)
            or not isinstance(self.limit, int)
            or isinstance(self.limit, bool)
            or not 1 <= self.limit <= MAX_LIMIT
        ):
            _bad("INVALID_SCHEMA")
        if (
            len(
                {
                    self.confirmed_source_identity_fingerprint,
                    self.prototype_source_identity_fingerprint,
                    self.hard_negative_identity_fingerprint,
                }
            )
            != 3
        ):
            _bad("INVALID_SCHEMA")
        _sealed(self)


@dataclass(frozen=True, slots=True, init=False)
class AuthorityEnvelope:
    query_fingerprint: str
    decision: PatternDecision
    exact_feedback_ref: str | None
    active_pattern_ids: tuple[str, ...]
    active_head_fingerprints: tuple[str, ...]
    consequential_version_fingerprint: str
    fingerprint: str
    version: str = HYBRID_RETRIEVAL_VERSION

    def __init__(self, *_: object, **__: object) -> None:
        raise HybridRetrievalError("INVALID_SCHEMA")

    def _validate(self) -> None:
        _refs(
            self.query_fingerprint, self.exact_feedback_ref, self.consequential_version_fingerprint
        )
        if not isinstance(self.decision, PatternDecision):
            _bad("INVALID_SCHEMA")
        _ref_tuple(self.active_pattern_ids)
        _ref_tuple(self.active_head_fingerprints)
        if len(self.active_pattern_ids) != len(self.active_head_fingerprints):
            _bad("INVALID_SCHEMA")
        source = self.decision.source
        if source is DecisionSource.EXACT_FEEDBACK:
            if (
                self.exact_feedback_ref is None
                or self.active_pattern_ids
                or self.active_head_fingerprints
                or self.decision.pattern_ids
            ):
                _bad("INVALID_SCHEMA")
        elif source is DecisionSource.ACTIVE_PATTERN:
            if (
                self.exact_feedback_ref is not None
                or not self.active_pattern_ids
                or self.active_pattern_ids != self.decision.pattern_ids
            ):
                _bad("INVALID_SCHEMA")
        elif source is DecisionSource.MANUAL:
            if (
                self.exact_feedback_ref is not None
                or self.active_pattern_ids != self.decision.pattern_ids
            ):
                _bad("INVALID_SCHEMA")
        else:
            _bad("INVALID_SCHEMA")
        _sealed(self)


@dataclass(frozen=True, slots=True)
class HybridEvidence:
    evidence_ref: str
    semantic_identity_fingerprint: str
    kind: EvidenceKind
    pattern_id: str | None
    outcome: OutcomeSignature
    tenant_ref: str
    project_ref: str | None
    document_type_fingerprint: str
    taxonomy_version_fingerprint: str
    scope_fingerprint: str
    consequential_version_fingerprint: str
    embedding_identity_fingerprint: str
    full_term_fingerprint: str
    confirmed: bool
    unit_compatible: bool
    critical_slots_compatible: bool
    replay_fingerprint: str | None
    owner_approval_ref: str | None
    activation_fingerprint: str | None
    contradiction_count: int
    supporting_refs: tuple[str, ...]
    matched_slot_kinds: tuple[str, ...]
    difference_codes: tuple[str, ...]
    fingerprint: str
    version: str = HYBRID_RETRIEVAL_VERSION

    def __post_init__(self) -> None:
        _refs(
            self.evidence_ref,
            self.semantic_identity_fingerprint,
            self.pattern_id,
            self.tenant_ref,
            self.project_ref,
            self.document_type_fingerprint,
            self.taxonomy_version_fingerprint,
            self.scope_fingerprint,
            self.consequential_version_fingerprint,
            self.embedding_identity_fingerprint,
            self.full_term_fingerprint,
            self.replay_fingerprint,
            self.owner_approval_ref,
            self.activation_fingerprint,
        )
        if (
            not isinstance(self.kind, EvidenceKind)
            or not isinstance(self.confirmed, bool)
            or not isinstance(self.unit_compatible, bool)
            or not isinstance(self.critical_slots_compatible, bool)
            or not isinstance(self.contradiction_count, int)
            or isinstance(self.contradiction_count, bool)
            or self.contradiction_count < 0
        ):
            _bad("INVALID_SCHEMA")
        _outcome(self.outcome)
        _ref_tuple(self.supporting_refs, MAX_REFS)
        _tokens(self.matched_slot_kinds)
        _tokens(self.difference_codes)
        lifecycle = (self.replay_fingerprint, self.owner_approval_ref, self.activation_fingerprint)
        if self.kind is EvidenceKind.CONFIRMED_EXAMPLE:
            if self.pattern_id is not None or any(lifecycle):
                _bad("INVALID_SCHEMA")
        elif self.pattern_id is None or not all(lifecycle) or self.contradiction_count != 0:
            _bad("INVALID_SCHEMA")
        _sealed(self)


@dataclass(frozen=True, slots=True)
class RankedSignal:
    channel: RetrievalChannel
    representation: RepresentationKind
    evidence_ref: str
    rank: int
    similarity_micros: int
    index_identity_fingerprint: str
    fingerprint: str
    version: str = HYBRID_RETRIEVAL_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.channel, RetrievalChannel) or not isinstance(
            self.representation, RepresentationKind
        ):
            _bad("INVALID_SCHEMA")
        _refs(self.evidence_ref, self.index_identity_fingerprint)
        if (
            not isinstance(self.rank, int)
            or isinstance(self.rank, bool)
            or self.rank < 1
            or not isinstance(self.similarity_micros, int)
            or isinstance(self.similarity_micros, bool)
            or not 0 <= self.similarity_micros <= SCORE_SCALE
        ):
            _bad("INVALID_SCHEMA")
        _sealed(self)


@dataclass(frozen=True, slots=True)
class SignalBatch:
    query_fingerprint: str
    channel: RetrievalChannel
    signals: tuple[RankedSignal, ...]
    unavailable: bool
    source_identity_fingerprint: str
    fingerprint: str
    version: str = HYBRID_RETRIEVAL_VERSION

    def __post_init__(self) -> None:
        _refs(self.query_fingerprint, self.source_identity_fingerprint)
        if (
            not isinstance(self.channel, RetrievalChannel)
            or not isinstance(self.signals, tuple)
            or len(self.signals) > MAX_SIGNALS
            or not isinstance(self.unavailable, bool)
        ):
            _bad("INVALID_SCHEMA")
        if self.unavailable and self.signals:
            _bad("INVALID_SCHEMA")
        if any(
            not isinstance(x, RankedSignal) or x.channel is not self.channel for x in self.signals
        ):
            _bad("INVALID_SCHEMA")
        if len({item.evidence_ref for item in self.signals}) != len(self.signals) or (
            len(self.signals) > 1
            and tuple(item.rank for item in self.signals) != tuple(range(1, len(self.signals) + 1))
        ):
            _bad("INVALID_SCHEMA")
        _sealed(self)


@dataclass(frozen=True, slots=True)
class HardNegativeHit:
    query_fingerprint: str
    positive_identity_fingerprint: str
    negative_ref: str
    source_pattern_id: str | None
    target_pattern_id: str | None
    edge_fingerprint: str
    representation: RepresentationKind
    rank: int
    similarity_micros: int
    direct_cannot_link: bool
    scope_fingerprint: str
    consequential_version_fingerprint: str
    difference_codes: tuple[str, ...]
    fingerprint: str
    version: str = HYBRID_RETRIEVAL_VERSION

    def __post_init__(self) -> None:
        _refs(
            self.query_fingerprint,
            self.positive_identity_fingerprint,
            self.negative_ref,
            self.source_pattern_id,
            self.target_pattern_id,
            self.edge_fingerprint,
            self.scope_fingerprint,
            self.consequential_version_fingerprint,
        )
        if (
            not isinstance(self.representation, RepresentationKind)
            or not isinstance(self.rank, int)
            or isinstance(self.rank, bool)
            or self.rank < 1
            or not isinstance(self.similarity_micros, int)
            or isinstance(self.similarity_micros, bool)
            or not 0 <= self.similarity_micros <= SCORE_SCALE
            or not isinstance(self.direct_cannot_link, bool)
        ):
            _bad("INVALID_SCHEMA")
        _tokens(self.difference_codes)
        _sealed(self)


@dataclass(frozen=True, slots=True)
class HardNegativeBatch:
    query_fingerprint: str
    hits: tuple[HardNegativeHit, ...]
    unavailable: bool
    source_identity_fingerprint: str
    fingerprint: str
    version: str = HYBRID_RETRIEVAL_VERSION

    def __post_init__(self) -> None:
        _refs(self.query_fingerprint, self.source_identity_fingerprint)
        if (
            not isinstance(self.hits, tuple)
            or len(self.hits) > MAX_HARD_NEGATIVES
            or not isinstance(self.unavailable, bool)
            or (self.unavailable and self.hits)
            or any(not isinstance(x, HardNegativeHit) for x in self.hits)
        ):
            _bad("INVALID_SCHEMA")
        if tuple(sorted(self.hits, key=_negative_key)) != self.hits:
            _bad("INVALID_SCHEMA")
        _sealed(self)


@dataclass(frozen=True, slots=True)
class RationalScore:
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.numerator, int)
            or isinstance(self.numerator, bool)
            or not isinstance(self.denominator, int)
            or isinstance(self.denominator, bool)
            or self.numerator < 0
            or self.denominator < 1
            or gcd(self.numerator, self.denominator) != 1
        ):
            _bad("INVALID_SCORE")


@dataclass(frozen=True, slots=True)
class HybridExplanation:
    reason_codes: tuple[ReasonCode, ...]
    positive_refs: tuple[str, ...]
    hard_negative_refs: tuple[str, ...]
    matched_slot_kinds: tuple[str, ...]
    difference_codes: tuple[str, ...]
    fingerprint: str
    version: str = HYBRID_RETRIEVAL_VERSION

    def __post_init__(self) -> None:
        if (
            not isinstance(self.reason_codes, tuple)
            or any(not isinstance(x, ReasonCode) for x in self.reason_codes)
            or self.reason_codes != tuple(sorted(set(self.reason_codes), key=lambda x: x.value))
        ):
            _bad("INVALID_SCHEMA")
        _ref_tuple(self.positive_refs)
        _ref_tuple(self.hard_negative_refs)
        _tokens(self.matched_slot_kinds)
        _tokens(self.difference_codes)
        _sealed(self)


@dataclass(frozen=True, slots=True)
class RankedHybridCandidate:
    semantic_identity_fingerprint: str
    evidence_refs: tuple[str, ...]
    outcome: OutcomeSignature
    score: RationalScore
    channel_count: int
    rank: int
    explanation: HybridExplanation
    fingerprint: str
    version: str = HYBRID_RETRIEVAL_VERSION

    def __post_init__(self) -> None:
        _refs(self.semantic_identity_fingerprint)
        _ref_tuple(self.evidence_refs)
        _outcome(self.outcome)
        if (
            not isinstance(self.score, RationalScore)
            or not isinstance(self.channel_count, int)
            or isinstance(self.channel_count, bool)
            or not 1 <= self.channel_count <= len(RetrievalChannel)
            or not isinstance(self.rank, int)
            or isinstance(self.rank, bool)
            or self.rank < 1
            or not isinstance(self.explanation, HybridExplanation)
        ):
            _bad("INVALID_SCHEMA")
        if self.evidence_refs != self.explanation.positive_refs:
            _bad("INVALID_SCHEMA")
        _sealed(self)


@dataclass(frozen=True, slots=True)
class HybridRetrievalResult:
    query_fingerprint: str
    status: HybridStatus
    authority: AuthorityEnvelope | None
    candidates: tuple[RankedHybridCandidate, ...]
    hard_negatives: tuple[HardNegativeHit, ...]
    unavailable_channels: tuple[RetrievalChannel, ...]
    requires_manual_review: bool
    auto_accepted: bool
    fingerprint: str
    version: str = HYBRID_RETRIEVAL_VERSION

    def __post_init__(self) -> None:
        _refs(self.query_fingerprint)
        if (
            not isinstance(self.status, HybridStatus)
            or (self.authority is not None and not isinstance(self.authority, AuthorityEnvelope))
            or not isinstance(self.candidates, tuple)
            or any(not isinstance(x, RankedHybridCandidate) for x in self.candidates)
            or not isinstance(self.hard_negatives, tuple)
            or any(not isinstance(x, HardNegativeHit) for x in self.hard_negatives)
            or not isinstance(self.requires_manual_review, bool)
            or not isinstance(self.auto_accepted, bool)
        ):
            _bad("INVALID_SCHEMA")
        if (
            len(self.candidates) > MAX_LIMIT
            or len({x.semantic_identity_fingerprint for x in self.candidates})
            != len(self.candidates)
            or tuple(x.rank for x in self.candidates) != tuple(range(1, len(self.candidates) + 1))
            or tuple(sorted(self.candidates, key=cmp_to_key(_candidate_compare))) != self.candidates
            or len(self.hard_negatives) > MAX_HARD_NEGATIVES
            or len({x.negative_ref for x in self.hard_negatives}) != len(self.hard_negatives)
            or tuple(sorted(self.hard_negatives, key=_negative_key)) != self.hard_negatives
            or any(x.query_fingerprint != self.query_fingerprint for x in self.hard_negatives)
            or not isinstance(self.unavailable_channels, tuple)
            or self.unavailable_channels
            != tuple(sorted(set(self.unavailable_channels), key=lambda x: x.value))
            or any(not isinstance(x, RetrievalChannel) for x in self.unavailable_channels)
        ):
            _bad("INVALID_SCHEMA")
        negative_refs = {item.negative_ref for item in self.hard_negatives}
        if any(
            not set(item.explanation.hard_negative_refs) <= negative_refs
            for item in self.candidates
        ):
            _bad("INVALID_SCHEMA")
        _result_state(self)
        _sealed(self)


def fingerprint(value: object) -> str:
    try:
        return (
            "sha256:"
            + hashlib.sha256(
                json.dumps(
                    _plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True
                ).encode()
            ).hexdigest()
        )
    except HybridRetrievalError:
        raise
    except (TypeError, ValueError) as exc:
        raise HybridRetrievalError("INVALID_SCHEMA") from exc


def resolve_authority(
    query: HybridQuery,
    *,
    exact_feedback: OutcomeSignature | None,
    exact_feedback_ref: str | None,
    matched_histories: tuple[RegistryHistory, ...],
    current_versions: PatternVersions,
    feedback_pattern_id: str | None = None,
) -> AuthorityEnvelope:
    if (
        not isinstance(query, HybridQuery)
        or not isinstance(matched_histories, tuple)
        or any(not isinstance(item, RegistryHistory) for item in matched_histories)
        or not isinstance(current_versions, PatternVersions)
    ):
        _bad("INVALID_SCHEMA")
    if exact_feedback is None:
        if exact_feedback_ref is not None:
            _bad("INVALID_SCHEMA")
    else:
        _outcome(exact_feedback)
        _refs(exact_feedback_ref)
        if exact_feedback_ref is None:
            _bad("INVALID_SCHEMA")
    _refs(feedback_pattern_id)
    try:
        decision = resolve_history_precedence(
            exact_feedback=exact_feedback,
            matched_histories=matched_histories,
            current_versions=current_versions,
            feedback_pattern_id=feedback_pattern_id,
        )
    except Exception as exc:
        raise HybridRetrievalError("INVALID_SCHEMA") from exc
    heads = tuple(
        sorted((item.head for item in matched_histories), key=lambda item: item.pattern_id)
    )
    selected = tuple(item for item in heads if item.pattern_id in decision.pattern_ids)
    if decision.source is DecisionSource.ACTIVE_PATTERN and (
        tuple(item.pattern_id for item in selected) != decision.pattern_ids
        or any(
            item.state is not PatternState.ACTIVE
            or item.versions != current_versions
            or item.expected_outcome != decision.outcome
            or item.replay is None
            or item.owner is None
            or item.activation is None
            or item.contradictions
            or item.risk_codes
            for item in selected
        )
    ):
        _bad("INVALID_SCHEMA")
    if (
        decision.source is DecisionSource.MANUAL
        and decision.pattern_ids
        and tuple(item.pattern_id for item in selected) != decision.pattern_ids
    ):
        _bad("INVALID_SCHEMA")
    envelope = object.__new__(AuthorityEnvelope)
    values = {
        "query_fingerprint": query.fingerprint,
        "decision": decision,
        "exact_feedback_ref": exact_feedback_ref,
        "active_pattern_ids": decision.pattern_ids,
        "active_head_fingerprints": tuple(item.fingerprint for item in selected),
        "consequential_version_fingerprint": query.consequential_version_fingerprint,
        "version": HYBRID_RETRIEVAL_VERSION,
    }
    for name, value in values.items():
        object.__setattr__(envelope, name, value)
    object.__setattr__(envelope, "fingerprint", fingerprint(values))
    envelope._validate()
    return envelope


def rank_hybrid(
    query: HybridQuery,
    *,
    authority: AuthorityEnvelope,
    evidence: tuple[HybridEvidence, ...],
    batches: tuple[SignalBatch, ...],
    hard_negative_batch: HardNegativeBatch,
) -> HybridRetrievalResult:
    if (
        not isinstance(query, HybridQuery)
        or not isinstance(authority, AuthorityEnvelope)
        or not isinstance(evidence, tuple)
        or len(evidence) > MAX_EVIDENCE
        or any(not isinstance(x, HybridEvidence) for x in evidence)
        or not isinstance(batches, tuple)
        or any(not isinstance(x, SignalBatch) for x in batches)
        or not isinstance(hard_negative_batch, HardNegativeBatch)
    ):
        _bad("INVALID_SCHEMA")
    if (
        authority.query_fingerprint != query.fingerprint
        or authority.consequential_version_fingerprint != query.consequential_version_fingerprint
    ):
        _bad("CONTEXT_MISMATCH")
    if authority.decision.source is DecisionSource.EXACT_FEEDBACK:
        return _result(query, HybridStatus.AUTHORITATIVE_EXACT, authority, (), (), (), False)
    if authority.decision.source is DecisionSource.ACTIVE_PATTERN:
        return _result(query, HybridStatus.AUTHORITATIVE_PATTERN, authority, (), (), (), False)
    if authority.active_pattern_ids:
        return _result(query, HybridStatus.REVIEW_REQUIRED, None, (), (), (), True)
    if not _complete_batches(query, batches) or not _valid_negative_batch(
        query, hard_negative_batch
    ):
        return _result(
            query,
            HybridStatus.UNAVAILABLE,
            None,
            (),
            (),
            tuple(sorted(RetrievalChannel, key=lambda x: x.value)),
            True,
        )
    by_ref = {x.evidence_ref: x for x in evidence}
    if len(by_ref) != len(evidence):
        _bad("DUPLICATE_EVIDENCE")
    usable: dict[str, list[RankedSignal]] = {}
    unavailable: list[RetrievalChannel] = []
    for batch in batches:
        if (
            batch.unavailable
            or batch.source_identity_fingerprint != _source_identity(query, batch.channel)
            or not _valid_batch(batch, by_ref, query)
        ):
            unavailable.append(batch.channel)
            continue
        for signal in batch.signals:
            record = by_ref[signal.evidence_ref]
            if not _eligible(record, query):
                continue
            usable.setdefault(record.semantic_identity_fingerprint, []).append(signal)
    if unavailable:
        return _result(
            query,
            HybridStatus.UNAVAILABLE,
            None,
            (),
            (),
            tuple(sorted(unavailable, key=lambda x: x.value)),
            True,
        )
    negative_by_identity: dict[str, list[HardNegativeHit]] = {}
    for hit in hard_negative_batch.hits:
        negative_by_identity.setdefault(hit.positive_identity_fingerprint, []).append(hit)
    candidates: list[RankedHybridCandidate] = []
    exposed: list[HardNegativeHit] = []
    for identity, signals in usable.items():
        best: dict[RetrievalChannel, RankedSignal] = {}
        for signal in signals:
            old = best.get(signal.channel)
            if old is None or (signal.rank, signal.evidence_ref) < (old.rank, old.evidence_ref):
                best[signal.channel] = signal
        chosen = list(best.values())
        records = [by_ref[x.evidence_ref] for x in chosen]
        if len({x.outcome for x in records}) != 1:
            _bad("OUTCOME_CONFLICT")
        hits = negative_by_identity.get(identity, [])
        direct = [x for x in hits if x.direct_cannot_link]
        if direct:
            exposed.append(min(direct, key=_negative_key))
            continue
        positive_by_representation: dict[RepresentationKind, int] = {}
        for signal in chosen:
            positive_by_representation[signal.representation] = max(
                signal.similarity_micros,
                positive_by_representation.get(signal.representation, 0),
            )
        blocker = [
            item
            for item in hits
            if item.representation in positive_by_representation
            and item.similarity_micros >= positive_by_representation[item.representation]
        ]
        exposed.extend(blocker)
        codes = {_channel_reason(x.channel) for x in chosen}
        if query.exact_only:
            codes.add(ReasonCode.EXACT_ONLY)
        slots = tuple(sorted({v for x in records for v in x.matched_slot_kinds}))
        if slots:
            codes.add(ReasonCode.SLOT_MATCH)
        if blocker:
            codes.add(ReasonCode.HARD_NEGATIVE_NEARER_OR_EQUAL)
        refs = tuple(sorted({x.evidence_ref for x in chosen}))
        num, den = _rrf(chosen)
        explanation = create_hybrid_explanation(
            reason_codes=tuple(sorted(codes, key=lambda x: x.value)),
            positive_refs=refs,
            hard_negative_refs=tuple(sorted({x.negative_ref for x in blocker})),
            matched_slot_kinds=slots,
            difference_codes=tuple(sorted({v for x in records for v in x.difference_codes})),
        )
        candidates.append(
            create_ranked_hybrid_candidate(
                semantic_identity_fingerprint=identity,
                evidence_refs=refs,
                outcome=records[0].outcome,
                score=RationalScore(num, den),
                channel_count=len(chosen),
                rank=1,
                explanation=explanation,
            )
        )
    candidates.sort(key=cmp_to_key(_candidate_compare))
    ranked = [
        create_ranked_hybrid_candidate(
            semantic_identity_fingerprint=x.semantic_identity_fingerprint,
            evidence_refs=x.evidence_refs,
            outcome=x.outcome,
            score=x.score,
            channel_count=x.channel_count,
            rank=index,
            explanation=x.explanation,
        )
        for index, x in enumerate(candidates[: query.limit], 1)
    ]
    return _result(
        query,
        HybridStatus.REVIEW_REQUIRED,
        None,
        tuple(ranked),
        tuple(sorted(set(exposed), key=_negative_key)),
        (),
        True,
    )


def _complete_batches(query: HybridQuery, batches: tuple[SignalBatch, ...]) -> bool:
    return (
        len(batches) == len(RetrievalChannel)
        and len({x.channel for x in batches}) == len(RetrievalChannel)
        and all(x.query_fingerprint == query.fingerprint for x in batches)
    )


def _valid_negative_batch(query: HybridQuery, batch: HardNegativeBatch) -> bool:
    return (
        batch.query_fingerprint == query.fingerprint
        and not batch.unavailable
        and batch.source_identity_fingerprint == query.hard_negative_identity_fingerprint
        and _canonical_hits(batch.hits, query)
    )


def _canonical_hits(hits: tuple[HardNegativeHit, ...], query: HybridQuery) -> bool:
    return tuple(sorted(hits, key=_negative_key)) == hits and all(
        x.query_fingerprint == query.fingerprint
        and x.scope_fingerprint == query.scope_fingerprint
        and x.consequential_version_fingerprint == query.consequential_version_fingerprint
        for x in hits
    )


def _valid_batch(
    batch: SignalBatch, evidence: dict[str, HybridEvidence], query: HybridQuery
) -> bool:
    if not isinstance(batch.signals, tuple) or any(
        not isinstance(x, RankedSignal) for x in batch.signals
    ):
        return False
    if (
        len(batch.signals) > MAX_SIGNALS
        or tuple(x.rank for x in batch.signals) != tuple(range(1, len(batch.signals) + 1))
        or len({x.evidence_ref for x in batch.signals}) != len(batch.signals)
    ):
        return False
    return all(
        x.index_identity_fingerprint
        == batch.source_identity_fingerprint
        == _source_identity(query, batch.channel)
        and x.evidence_ref in evidence
        and _matrix(x, evidence[x.evidence_ref])
        and _context(evidence[x.evidence_ref], query)
        for x in batch.signals
    )


def _matrix(signal: RankedSignal, evidence: HybridEvidence) -> bool:
    return {
        RetrievalChannel.PATTERN_MASK: (
            RepresentationKind.SEMANTIC_SKELETON,
            EvidenceKind.ACTIVE_PATTERN_PROTOTYPE,
        ),
        RetrievalChannel.LEXICAL: (RepresentationKind.FULL_TERM, EvidenceKind.CONFIRMED_EXAMPLE),
        RetrievalChannel.DENSE_FULL_TERM: (
            RepresentationKind.FULL_TERM,
            EvidenceKind.CONFIRMED_EXAMPLE,
        ),
        RetrievalChannel.DENSE_SEMANTIC_SKELETON: (
            RepresentationKind.SEMANTIC_SKELETON,
            EvidenceKind.CONFIRMED_EXAMPLE,
        ),
        RetrievalChannel.PROTOTYPE_FULL_TERM: (
            RepresentationKind.FULL_TERM,
            EvidenceKind.ACTIVE_PATTERN_PROTOTYPE,
        ),
        RetrievalChannel.PROTOTYPE_SEMANTIC_SKELETON: (
            RepresentationKind.SEMANTIC_SKELETON,
            EvidenceKind.ACTIVE_PATTERN_PROTOTYPE,
        ),
    }[signal.channel] == (signal.representation, evidence.kind)


def _context(x: HybridEvidence, q: HybridQuery) -> bool:
    return (
        x.tenant_ref,
        x.project_ref,
        x.document_type_fingerprint,
        x.taxonomy_version_fingerprint,
        x.scope_fingerprint,
        x.consequential_version_fingerprint,
        x.embedding_identity_fingerprint,
    ) == (
        q.tenant_ref,
        q.project_ref,
        q.document_type_fingerprint,
        q.taxonomy_version_fingerprint,
        q.scope_fingerprint,
        q.consequential_version_fingerprint,
        q.embedding_identity_fingerprint,
    )


def _eligible(x: HybridEvidence, q: HybridQuery) -> bool:
    return (
        x.confirmed
        and x.unit_compatible
        and x.critical_slots_compatible
        and x.contradiction_count == 0
        and (not q.exact_only or x.full_term_fingerprint == q.full_term_fingerprint)
    )


def _source_identity(query: HybridQuery, channel: RetrievalChannel) -> str:
    if channel in {
        RetrievalChannel.PATTERN_MASK,
        RetrievalChannel.PROTOTYPE_FULL_TERM,
        RetrievalChannel.PROTOTYPE_SEMANTIC_SKELETON,
    }:
        return query.prototype_source_identity_fingerprint
    return query.confirmed_source_identity_fingerprint


def _rrf(signals: list[RankedSignal]) -> tuple[int, int]:
    n, d = 0, 1
    for x in signals:
        p = RRF_K + x.rank
        n, d = n * p + d, d * p
        divisor = gcd(n, d)
        n //= divisor
        d //= divisor
    return n, d


def _candidate_compare(a: RankedHybridCandidate, b: RankedHybridCandidate) -> int:
    delta = a.score.numerator * b.score.denominator - b.score.numerator * a.score.denominator
    if delta:
        return -1 if delta > 0 else 1
    if a.channel_count != b.channel_count:
        return -1 if a.channel_count > b.channel_count else 1
    return (a.semantic_identity_fingerprint > b.semantic_identity_fingerprint) - (
        a.semantic_identity_fingerprint < b.semantic_identity_fingerprint
    )


def _negative_key(x: HardNegativeHit) -> tuple[str, int, int, str, str]:
    return (
        x.positive_identity_fingerprint,
        x.rank,
        -x.similarity_micros,
        x.negative_ref,
        x.fingerprint,
    )


def _channel_reason(x: RetrievalChannel) -> ReasonCode:
    return {
        RetrievalChannel.PATTERN_MASK: ReasonCode.PATTERN_MASK_MATCH,
        RetrievalChannel.LEXICAL: ReasonCode.LEXICAL_MATCH,
        RetrievalChannel.DENSE_FULL_TERM: ReasonCode.DENSE_FULL_TERM_MATCH,
        RetrievalChannel.DENSE_SEMANTIC_SKELETON: ReasonCode.DENSE_SEMANTIC_SKELETON_MATCH,
        RetrievalChannel.PROTOTYPE_FULL_TERM: ReasonCode.PROTOTYPE_FULL_TERM_MATCH,
        RetrievalChannel.PROTOTYPE_SEMANTIC_SKELETON: ReasonCode.PROTOTYPE_SEMANTIC_SKELETON_MATCH,
    }[x]


def _result(
    q: HybridQuery,
    status: HybridStatus,
    authority: AuthorityEnvelope | None,
    candidates: tuple[RankedHybridCandidate, ...],
    negatives: tuple[HardNegativeHit, ...],
    unavailable: tuple[RetrievalChannel, ...],
    review: bool,
) -> HybridRetrievalResult:
    return create_hybrid_retrieval_result(
        query_fingerprint=q.fingerprint,
        status=status,
        authority=authority,
        candidates=candidates,
        hard_negatives=negatives,
        unavailable_channels=unavailable,
        requires_manual_review=review,
        auto_accepted=False,
    )


def _result_state(x: HybridRetrievalResult) -> None:
    if x.status in {HybridStatus.AUTHORITATIVE_EXACT, HybridStatus.AUTHORITATIVE_PATTERN}:
        expected = (
            DecisionSource.EXACT_FEEDBACK
            if x.status is HybridStatus.AUTHORITATIVE_EXACT
            else DecisionSource.ACTIVE_PATTERN
        )
        if (
            x.authority is None
            or x.authority.query_fingerprint != x.query_fingerprint
            or x.authority.decision.source is not expected
            or x.auto_accepted
            or x.requires_manual_review
            or x.candidates
            or x.hard_negatives
            or x.unavailable_channels
        ):
            _bad("INVALID_SCHEMA")
    elif x.authority is not None or x.auto_accepted or not x.requires_manual_review:
        _bad("INVALID_SCHEMA")
    if x.status is HybridStatus.UNAVAILABLE and x.candidates:
        _bad("INVALID_SCHEMA")


def _factory(cls: type[Any], values: dict[str, object]) -> Any:
    names = {x.name for x in fields(cls)}
    if "fingerprint" in values or set(values) - (names - {"fingerprint"}):
        _bad("INVALID_SCHEMA")
    payload = {**values, "version": values.get("version", HYBRID_RETRIEVAL_VERSION)}
    if set(payload) != names - {"fingerprint"}:
        _bad("INVALID_SCHEMA")
    return cls(**payload, fingerprint=fingerprint(payload))


def create_hybrid_query(**values: object) -> HybridQuery:
    return _factory(HybridQuery, values)


def create_hybrid_evidence(**values: object) -> HybridEvidence:
    return _factory(HybridEvidence, values)


def create_ranked_signal(**values: object) -> RankedSignal:
    return _factory(RankedSignal, values)


def create_signal_batch(**values: object) -> SignalBatch:
    return _factory(SignalBatch, values)


def create_hard_negative_hit(**values: object) -> HardNegativeHit:
    return _factory(HardNegativeHit, values)


def create_hard_negative_batch(**values: object) -> HardNegativeBatch:
    return _factory(HardNegativeBatch, values)


def create_hybrid_explanation(**values: object) -> HybridExplanation:
    return _factory(HybridExplanation, values)


def create_ranked_hybrid_candidate(**values: object) -> RankedHybridCandidate:
    return _factory(RankedHybridCandidate, values)


def create_hybrid_retrieval_result(**values: object) -> HybridRetrievalResult:
    return _factory(HybridRetrievalResult, values)


def _sealed(x: object) -> None:
    if getattr(x, "version", None) != HYBRID_RETRIEVAL_VERSION:
        _bad("INVALID_SCHEMA")
    _refs(getattr(x, "fingerprint", None))
    payload = {f.name: getattr(x, f.name) for f in fields(x) if f.name != "fingerprint"}
    if x.fingerprint != fingerprint(payload):
        _bad("FINGERPRINT_MISMATCH")


def _refs(*values: object) -> None:
    for value in values:
        if value is not None and (not isinstance(value, str) or not _HASH.fullmatch(value)):
            _bad("INVALID_SCHEMA")


def _ref_tuple(values: object, maximum: int = MAX_CODES) -> None:
    if (
        not isinstance(values, tuple)
        or len(values) > maximum
        or any(not isinstance(x, str) or not _HASH.fullmatch(x) for x in values)
        or values != tuple(sorted(set(values)))
    ):
        _bad("INVALID_SCHEMA")


def _tokens(values: object) -> None:
    if (
        not isinstance(values, tuple)
        or len(values) > MAX_CODES
        or any(not isinstance(x, str) or not _TOKEN.fullmatch(x) for x in values)
        or values != tuple(sorted(set(values)))
    ):
        _bad("INVALID_SCHEMA")


def _outcome(value: object) -> None:
    if not isinstance(value, OutcomeSignature) or value.action not in {"accept", "reject"}:
        _bad("INVALID_SCHEMA")
    if value.action == "reject":
        if value.mode is not None or value.target_category is not None:
            _bad("INVALID_SCHEMA")
        return
    if (
        value.mode not in {"quantity_cost", "cost_only"}
        or not isinstance(value.target_category, str)
        or not _TOKEN.fullmatch(value.target_category)
    ):
        _bad("INVALID_SCHEMA")


def _plain(value: object) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if is_dataclass(value):
        return {k: _plain(v) for k, v in asdict(value).items()}
    if isinstance(value, tuple):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        if not all(isinstance(k, str) for k in value):
            _bad("INVALID_SCHEMA")
        return {k: _plain(v) for k, v in value.items()}
    if value is None or isinstance(value, (str, int, bool)):
        return value
    _bad("INVALID_SCHEMA")


def _bad(code: str) -> None:
    raise HybridRetrievalError(code)
