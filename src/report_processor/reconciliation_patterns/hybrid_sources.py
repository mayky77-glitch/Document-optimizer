"""Read-only transient source adapter for ``HybridRetrieval-1.0``."""

from __future__ import annotations

import re
from dataclasses import dataclass
from math import isfinite
from typing import Protocol

from report_processor.stage_rag.models import DenseRetrievalResult
from report_processor.work_semantics.semantic_skeleton import build_semantic_skeleton

from .feedback_graph import FeedbackGraph, export_hard_negative_index
from .hybrid_retrieval import (
    MAX_HARD_NEGATIVES,
    MAX_SIGNALS,
    SCORE_SCALE,
    AuthorityEnvelope,
    EvidenceKind,
    HardNegativeBatch,
    HybridEvidence,
    HybridQuery,
    RankedSignal,
    RepresentationKind,
    RetrievalChannel,
    SignalBatch,
    create_hard_negative_batch,
    create_hard_negative_hit,
    create_ranked_signal,
    create_signal_batch,
    fingerprint,
)
from .pattern_models import PatternState, PatternVersions
from .pattern_registry import DecisionSource, RegistryHistory

HYBRID_SOURCES_VERSION = "HybridSources-1.0"

_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_TOKEN = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")


class HybridSourceError(ValueError):
    """Stable adapter error without provider or input material."""

    def __init__(self, code: str) -> None:
        super().__init__("hybrid source input is invalid")
        self.code = code


@dataclass(frozen=True, slots=True)
class SourceMatch:
    """One privacy-safe ranked provider match."""

    evidence_ref: str
    rank: int
    similarity_micros: int

    def __post_init__(self) -> None:
        if (
            not _is_hash(self.evidence_ref)
            or not _positive_int(self.rank)
            or not _micros(self.similarity_micros)
        ):
            _bad("INVALID_SCHEMA")


@dataclass(frozen=True, slots=True)
class HardNegativeMatch:
    """One safe negative neighbour awaiting graph-direction attestation."""

    positive_identity_fingerprint: str
    negative_ref: str
    source_pattern_id: str
    target_pattern_id: str
    edge_fingerprint: str
    representation: RepresentationKind
    rank: int
    similarity_micros: int
    difference_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not all(
                _is_hash(value)
                for value in (
                    self.positive_identity_fingerprint,
                    self.negative_ref,
                    self.source_pattern_id,
                    self.target_pattern_id,
                    self.edge_fingerprint,
                )
            )
            or self.source_pattern_id == self.target_pattern_id
            or not isinstance(self.representation, RepresentationKind)
            or not _positive_int(self.rank)
            or not _micros(self.similarity_micros)
            or not _tokens(self.difference_codes)
        ):
            _bad("INVALID_SCHEMA")


@dataclass(frozen=True, slots=True)
class HybridSourceBundle:
    """Only sealed core batches; no raw provider material or decision state."""

    batches: tuple[SignalBatch, ...]
    hard_negative_batch: HardNegativeBatch
    fingerprint: str
    version: str = HYBRID_SOURCES_VERSION

    def __post_init__(self) -> None:
        channels = tuple(sorted(RetrievalChannel, key=lambda item: item.value))
        if (
            self.version != HYBRID_SOURCES_VERSION
            or not isinstance(self.batches, tuple)
            or len(self.batches) != len(channels)
            or any(not isinstance(item, SignalBatch) for item in self.batches)
            or tuple(item.channel for item in self.batches) != channels
            or len({item.query_fingerprint for item in self.batches}) != 1
            or not isinstance(self.hard_negative_batch, HardNegativeBatch)
            or self.hard_negative_batch.query_fingerprint != self.batches[0].query_fingerprint
            or not _is_hash(self.fingerprint)
            or self.fingerprint != _bundle_fingerprint(self)
        ):
            _bad("INVALID_SCHEMA")


class OpaqueBinder(Protocol):
    """Binds transient provider/context values to opaque public fingerprints."""

    def bind(self, namespace: str, value: str | None) -> str | None: ...


class RankedSource(Protocol):
    @property
    def index_identity(self) -> str: ...

    def retrieve(self, *args: object, **kwargs: object) -> tuple[SourceMatch, ...]: ...


class DenseSource(Protocol):
    @property
    def index_identity(self) -> str: ...

    def retrieve(self, *args: object, **kwargs: object) -> DenseRetrievalResult: ...


class HardNegativeSource(Protocol):
    @property
    def index_identity(self) -> str: ...

    def retrieve(self, *args: object, **kwargs: object) -> tuple[HardNegativeMatch, ...]: ...


def collect_hybrid_sources(
    query: HybridQuery,
    *,
    authority: AuthorityEnvelope,
    normalized_term: str,
    tenant_id: str,
    project_id: str | None,
    document_type: str,
    taxonomy_version: str,
    category: str | None,
    object_kind: str | None,
    binder: OpaqueBinder,
    current_versions: PatternVersions,
    confirmed_evidence: tuple[HybridEvidence, ...],
    prototype_evidence: tuple[HybridEvidence, ...],
    prototype_histories: tuple[RegistryHistory, ...],
    feedback_graph: FeedbackGraph,
    pattern_mask_source: RankedSource,
    lexical_source: RankedSource,
    confirmed_dense_source: DenseSource,
    prototype_dense_source: DenseSource,
    hard_negative_source: HardNegativeSource,
) -> HybridSourceBundle:
    """Collect assistive batches without ranking, applying, or persisting decisions."""
    _boundary(
        query,
        authority,
        normalized_term,
        tenant_id,
        project_id,
        document_type,
        taxonomy_version,
        binder,
        current_versions,
        confirmed_evidence,
        prototype_evidence,
        prototype_histories,
        feedback_graph,
    )
    if _authority_suppresses(authority):
        return _unavailable_bundle(query)
    try:
        skeleton_text = build_semantic_skeleton(
            normalized_term, category=category, object_kind=object_kind
        ).skeleton_text
    except Exception:
        return _unavailable_bundle(query)
    if not _context_bound(
        query,
        binder,
        normalized_term=normalized_term,
        skeleton_text=skeleton_text,
        tenant_id=tenant_id,
        project_id=project_id,
        document_type=document_type,
        taxonomy_version=taxonomy_version,
    ):
        return _unavailable_bundle(query)

    confirmed = _evidence_map(confirmed_evidence, EvidenceKind.CONFIRMED_EXAMPLE)
    prototypes = _evidence_map(prototype_evidence, EvidenceKind.ACTIVE_PATTERN_PROTOTYPE)
    prototype_ready = _prototype_ready(prototypes, prototype_histories, current_versions, query)
    provider_kwargs = {
        "limit": query.limit,
        "tenant_id": tenant_id,
        "project_id": project_id,
        "document_type": document_type,
        "taxonomy_version": taxonomy_version,
    }
    batches = (
        _ranked_batch(
            query,
            binder,
            channel=RetrievalChannel.PATTERN_MASK,
            representation=RepresentationKind.SEMANTIC_SKELETON,
            source=pattern_mask_source,
            text=skeleton_text,
            evidence=prototypes,
            expected_source=query.prototype_source_identity_fingerprint,
            source_namespace="prototype_source_identity_fingerprint",
            provider_kwargs=provider_kwargs,
            source_allowed=prototype_ready,
        ),
        _ranked_batch(
            query,
            binder,
            channel=RetrievalChannel.LEXICAL,
            representation=RepresentationKind.FULL_TERM,
            source=lexical_source,
            text=normalized_term,
            evidence=confirmed,
            expected_source=query.confirmed_source_identity_fingerprint,
            source_namespace="confirmed_source_identity_fingerprint",
            provider_kwargs=provider_kwargs,
            source_allowed=True,
        ),
        _dense_batch(
            query,
            binder,
            channel=RetrievalChannel.DENSE_FULL_TERM,
            representation=RepresentationKind.FULL_TERM,
            source=confirmed_dense_source,
            text=normalized_term,
            evidence=confirmed,
            evidence_namespace="confirmed_evidence_ref",
            expected_category=category,
            expected_source=query.confirmed_source_identity_fingerprint,
            source_namespace="confirmed_source_identity_fingerprint",
            provider_kwargs=provider_kwargs,
            source_allowed=True,
        ),
        _dense_batch(
            query,
            binder,
            channel=RetrievalChannel.DENSE_SEMANTIC_SKELETON,
            representation=RepresentationKind.SEMANTIC_SKELETON,
            source=confirmed_dense_source,
            text=skeleton_text,
            evidence=confirmed,
            evidence_namespace="confirmed_evidence_ref",
            expected_category=category,
            expected_source=query.confirmed_source_identity_fingerprint,
            source_namespace="confirmed_source_identity_fingerprint",
            provider_kwargs=provider_kwargs,
            source_allowed=True,
        ),
        _dense_batch(
            query,
            binder,
            channel=RetrievalChannel.PROTOTYPE_FULL_TERM,
            representation=RepresentationKind.FULL_TERM,
            source=prototype_dense_source,
            text=normalized_term,
            evidence=prototypes,
            evidence_namespace="prototype_evidence_ref",
            expected_category=category,
            expected_source=query.prototype_source_identity_fingerprint,
            source_namespace="prototype_source_identity_fingerprint",
            provider_kwargs=provider_kwargs,
            source_allowed=prototype_ready,
        ),
        _dense_batch(
            query,
            binder,
            channel=RetrievalChannel.PROTOTYPE_SEMANTIC_SKELETON,
            representation=RepresentationKind.SEMANTIC_SKELETON,
            source=prototype_dense_source,
            text=skeleton_text,
            evidence=prototypes,
            evidence_namespace="prototype_evidence_ref",
            expected_category=category,
            expected_source=query.prototype_source_identity_fingerprint,
            source_namespace="prototype_source_identity_fingerprint",
            provider_kwargs=provider_kwargs,
            source_allowed=prototype_ready,
        ),
    )
    ordered = tuple(sorted(batches, key=lambda item: item.channel.value))
    negatives = _negative_batch(
        query,
        binder,
        source=hard_negative_source,
        normalized_term=normalized_term,
        skeleton_text=skeleton_text,
        evidence={**confirmed, **prototypes},
        feedback_graph=feedback_graph,
        provider_kwargs=provider_kwargs,
    )
    return _bundle(ordered, negatives)


def _boundary(
    query: object,
    authority: object,
    normalized_term: object,
    tenant_id: object,
    project_id: object,
    document_type: object,
    taxonomy_version: object,
    binder: object,
    current_versions: object,
    confirmed_evidence: object,
    prototype_evidence: object,
    prototype_histories: object,
    feedback_graph: object,
) -> None:
    if (
        not isinstance(query, HybridQuery)
        or not isinstance(authority, AuthorityEnvelope)
        or authority.query_fingerprint != query.fingerprint
        or not isinstance(normalized_term, str)
        or not normalized_term.strip()
        or not isinstance(tenant_id, str)
        or not tenant_id
        or (project_id is not None and not isinstance(project_id, str))
        or not isinstance(document_type, str)
        or not isinstance(taxonomy_version, str)
        or not callable(getattr(binder, "bind", None))
        or not isinstance(current_versions, PatternVersions)
        or not _typed_tuple(confirmed_evidence, HybridEvidence)
        or not _typed_tuple(prototype_evidence, HybridEvidence)
        or not _typed_tuple(prototype_histories, RegistryHistory)
        or not isinstance(feedback_graph, FeedbackGraph)
    ):
        _bad("INVALID_SCHEMA")


def _authority_suppresses(authority: AuthorityEnvelope) -> bool:
    return authority.decision.source in {
        DecisionSource.EXACT_FEEDBACK,
        DecisionSource.ACTIVE_PATTERN,
    } or bool(authority.active_pattern_ids)


def _context_bound(
    query: HybridQuery,
    binder: OpaqueBinder,
    *,
    normalized_term: str,
    skeleton_text: str,
    tenant_id: str,
    project_id: str | None,
    document_type: str,
    taxonomy_version: str,
) -> bool:
    expected = (
        ("tenant_ref", tenant_id, query.tenant_ref),
        ("project_ref", project_id, query.project_ref),
        ("document_type_fingerprint", document_type, query.document_type_fingerprint),
        ("taxonomy_version_fingerprint", taxonomy_version, query.taxonomy_version_fingerprint),
        ("full_term_fingerprint", normalized_term, query.full_term_fingerprint),
        ("skeleton_fingerprint", skeleton_text, query.skeleton_fingerprint),
    )
    try:
        return all(binder.bind(namespace, raw) == opaque for namespace, raw, opaque in expected)
    except Exception:
        return False


def _evidence_map(
    values: tuple[HybridEvidence, ...], kind: EvidenceKind
) -> dict[str, HybridEvidence]:
    result = {value.evidence_ref: value for value in values}
    if len(result) != len(values) or any(value.kind is not kind for value in values):
        _bad("INVALID_SCHEMA")
    return result


def _prototype_ready(
    evidence: dict[str, HybridEvidence],
    histories: tuple[RegistryHistory, ...],
    versions: PatternVersions,
    query: HybridQuery,
) -> bool:
    by_pattern = {history.head.pattern_id: history.head for history in histories}
    if len(by_pattern) != len(histories):
        return False
    for value in evidence.values():
        head = by_pattern.get(value.pattern_id or "")
        if (
            head is None
            or head.state is not PatternState.ACTIVE
            or head.versions != versions
            or head.expected_outcome != value.outcome
            or head.owner is None
            or head.activation is None
            or head.owner.approval_ref != value.owner_approval_ref
            or head.activation.activation_fingerprint != value.activation_fingerprint
            or head.contradictions
            or head.risk_codes
            or not _eligible(value, query)
        ):
            return False
    return True


def _ranked_batch(
    query: HybridQuery,
    binder: OpaqueBinder,
    *,
    channel: RetrievalChannel,
    representation: RepresentationKind,
    source: RankedSource,
    text: str,
    evidence: dict[str, HybridEvidence],
    expected_source: str,
    source_namespace: str,
    provider_kwargs: dict[str, object],
    source_allowed: bool,
) -> SignalBatch:
    if not source_allowed or not _source_bound(binder, source, source_namespace, expected_source):
        return _empty_batch(query, channel, expected_source, unavailable=True)
    try:
        values = source.retrieve(text, **provider_kwargs)
        if not isinstance(values, tuple) or any(
            not isinstance(value, SourceMatch) for value in values
        ):
            raise TypeError
        ordered = tuple(sorted(values, key=lambda value: (value.rank, value.evidence_ref)))
        if (
            len(ordered) > MAX_SIGNALS
            or tuple(value.rank for value in ordered) != tuple(range(1, len(ordered) + 1))
            or len({value.evidence_ref for value in ordered}) != len(ordered)
            or any(
                value.evidence_ref not in evidence
                or not _eligible(evidence[value.evidence_ref], query)
                for value in ordered
            )
        ):
            raise ValueError
        signals = tuple(
            create_ranked_signal(
                channel=channel,
                representation=representation,
                evidence_ref=value.evidence_ref,
                rank=value.rank,
                similarity_micros=value.similarity_micros,
                index_identity_fingerprint=expected_source,
            )
            for value in ordered
        )
        return _make_batch(query, channel, signals, expected_source, unavailable=False)
    except Exception:
        return _empty_batch(query, channel, expected_source, unavailable=True)


def _dense_batch(
    query: HybridQuery,
    binder: OpaqueBinder,
    *,
    channel: RetrievalChannel,
    representation: RepresentationKind,
    source: DenseSource,
    text: str,
    evidence: dict[str, HybridEvidence],
    evidence_namespace: str,
    expected_category: str | None,
    expected_source: str,
    source_namespace: str,
    provider_kwargs: dict[str, object],
    source_allowed: bool,
) -> SignalBatch:
    if not source_allowed or not _source_bound(binder, source, source_namespace, expected_source):
        return _empty_batch(query, channel, expected_source, unavailable=True)
    try:
        result = source.retrieve(
            provider_kwargs["tenant_id"],
            text,
            limit=provider_kwargs["limit"],
            project_id=provider_kwargs["project_id"],
            document_type=provider_kwargs["document_type"],
            taxonomy_version=provider_kwargs["taxonomy_version"],
        )
        if (
            not isinstance(result, DenseRetrievalResult)
            or result.unavailable
            or result.index_identity != source.index_identity
            or not _dense_query_bound(result, provider_kwargs, binder, query)
            or len(result.candidates) > MAX_SIGNALS
        ):
            raise ValueError
        signals: list[RankedSignal] = []
        seen: set[str] = set()
        for rank, candidate in enumerate(result.candidates, 1):
            evidence_ref = binder.bind(evidence_namespace, candidate.example_id)
            if (
                not isinstance(evidence_ref, str)
                or evidence_ref in seen
                or evidence_ref not in evidence
                or candidate.review_decision != "confirmed"
                or candidate.taxonomy_version != provider_kwargs["taxonomy_version"]
            ):
                raise ValueError
            if expected_category is not None and candidate.category != expected_category:
                raise ValueError
            score = float(candidate.score)
            if not isfinite(score) or not 0 <= score <= 1:
                raise ValueError
            if not _eligible(evidence[evidence_ref], query):
                raise ValueError
            seen.add(evidence_ref)
            signals.append(
                create_ranked_signal(
                    channel=channel,
                    representation=representation,
                    evidence_ref=evidence_ref,
                    rank=rank,
                    similarity_micros=round(score * SCORE_SCALE),
                    index_identity_fingerprint=expected_source,
                )
            )
        return _make_batch(query, channel, tuple(signals), expected_source, unavailable=False)
    except Exception:
        return _empty_batch(query, channel, expected_source, unavailable=True)


def _dense_query_bound(
    result: DenseRetrievalResult,
    provider_kwargs: dict[str, object],
    binder: OpaqueBinder,
    query: HybridQuery,
) -> bool:
    dense_query = result.query
    identity = (
        f"{dense_query.embedding_model_id}|{dense_query.embedding_model_revision}|"
        f"{dense_query.embedding_dimensions}"
    )
    try:
        return (
            dense_query.tenant_id == provider_kwargs["tenant_id"]
            and dense_query.project_id == provider_kwargs["project_id"]
            and dense_query.document_type == provider_kwargs["document_type"]
            and dense_query.taxonomy_version == provider_kwargs["taxonomy_version"]
            and binder.bind("embedding_identity_fingerprint", identity)
            == query.embedding_identity_fingerprint
        )
    except Exception:
        return False


def _negative_batch(
    query: HybridQuery,
    binder: OpaqueBinder,
    *,
    source: HardNegativeSource,
    normalized_term: str,
    skeleton_text: str,
    evidence: dict[str, HybridEvidence],
    feedback_graph: FeedbackGraph,
    provider_kwargs: dict[str, object],
) -> HardNegativeBatch:
    expected_source = query.hard_negative_identity_fingerprint
    if not _source_bound(binder, source, "hard_negative_identity_fingerprint", expected_source):
        return _empty_negative(query, unavailable=True)
    try:
        values = source.retrieve(normalized_term, skeleton_text, **provider_kwargs)
        if (
            not isinstance(values, tuple)
            or len(values) > MAX_HARD_NEGATIVES
            or any(not isinstance(value, HardNegativeMatch) for value in values)
        ):
            raise TypeError
        index = export_hard_negative_index(feedback_graph)
        allowed = {
            (item.source_pattern_id, item.target_pattern_id, item.edge_fingerprint)
            for item in index.entries
        }
        selected = tuple(
            sorted(
                (
                    value
                    for value in values
                    if (
                        value.source_pattern_id,
                        value.target_pattern_id,
                        value.edge_fingerprint,
                    )
                    in allowed
                    and value.positive_identity_fingerprint
                    in {item.semantic_identity_fingerprint for item in evidence.values()}
                ),
                key=lambda value: (
                    value.rank,
                    -value.similarity_micros,
                    value.negative_ref,
                ),
            )
        )
        hits = tuple(
            create_hard_negative_hit(
                query_fingerprint=query.fingerprint,
                positive_identity_fingerprint=value.positive_identity_fingerprint,
                negative_ref=value.negative_ref,
                source_pattern_id=value.source_pattern_id,
                target_pattern_id=value.target_pattern_id,
                edge_fingerprint=value.edge_fingerprint,
                representation=value.representation,
                rank=rank,
                similarity_micros=value.similarity_micros,
                direct_cannot_link=True,
                scope_fingerprint=query.scope_fingerprint,
                consequential_version_fingerprint=query.consequential_version_fingerprint,
                difference_codes=value.difference_codes,
            )
            for rank, value in enumerate(selected, 1)
        )
        ordered = tuple(
            sorted(
                hits,
                key=lambda value: (
                    value.positive_identity_fingerprint,
                    value.rank,
                    -value.similarity_micros,
                    value.negative_ref,
                    value.fingerprint,
                ),
            )
        )
        return create_hard_negative_batch(
            query_fingerprint=query.fingerprint,
            hits=ordered,
            unavailable=False,
            source_identity_fingerprint=expected_source,
        )
    except Exception:
        return _empty_negative(query, unavailable=True)


def _source_bound(
    binder: OpaqueBinder,
    source: object,
    namespace: str,
    expected: str,
) -> bool:
    try:
        identity = source.index_identity
        return isinstance(identity, str) and binder.bind(namespace, identity) == expected
    except Exception:
        return False


def _eligible(value: HybridEvidence, query: HybridQuery) -> bool:
    return (
        (
            value.tenant_ref,
            value.project_ref,
            value.document_type_fingerprint,
            value.taxonomy_version_fingerprint,
            value.scope_fingerprint,
            value.consequential_version_fingerprint,
            value.embedding_identity_fingerprint,
        )
        == (
            query.tenant_ref,
            query.project_ref,
            query.document_type_fingerprint,
            query.taxonomy_version_fingerprint,
            query.scope_fingerprint,
            query.consequential_version_fingerprint,
            query.embedding_identity_fingerprint,
        )
        and value.confirmed
        and value.unit_compatible
        and value.critical_slots_compatible
        and value.contradiction_count == 0
        and (not query.exact_only or value.full_term_fingerprint == query.full_term_fingerprint)
    )


def _unavailable_bundle(query: HybridQuery) -> HybridSourceBundle:
    batches = tuple(
        _empty_batch(
            query,
            channel,
            _source_identity(query, channel),
            unavailable=True,
        )
        for channel in sorted(RetrievalChannel, key=lambda item: item.value)
    )
    return _bundle(batches, _empty_negative(query, unavailable=True))


def _empty_batch(
    query: HybridQuery,
    channel: RetrievalChannel,
    source_identity: str,
    *,
    unavailable: bool,
) -> SignalBatch:
    return _make_batch(query, channel, (), source_identity, unavailable=unavailable)


def _make_batch(
    query: HybridQuery,
    channel: RetrievalChannel,
    signals: tuple[RankedSignal, ...],
    source_identity: str,
    *,
    unavailable: bool,
) -> SignalBatch:
    return create_signal_batch(
        query_fingerprint=query.fingerprint,
        channel=channel,
        signals=signals,
        unavailable=unavailable,
        source_identity_fingerprint=source_identity,
    )


def _empty_negative(query: HybridQuery, *, unavailable: bool) -> HardNegativeBatch:
    return create_hard_negative_batch(
        query_fingerprint=query.fingerprint,
        hits=(),
        unavailable=unavailable,
        source_identity_fingerprint=query.hard_negative_identity_fingerprint,
    )


def _bundle(batches: tuple[SignalBatch, ...], negative: HardNegativeBatch) -> HybridSourceBundle:
    payload = {
        "batches": batches,
        "hard_negative_batch": negative,
        "version": HYBRID_SOURCES_VERSION,
    }
    return HybridSourceBundle(batches, negative, fingerprint(payload))


def _bundle_fingerprint(value: HybridSourceBundle) -> str:
    return fingerprint(
        {
            "batches": value.batches,
            "hard_negative_batch": value.hard_negative_batch,
            "version": value.version,
        }
    )


def _source_identity(query: HybridQuery, channel: RetrievalChannel) -> str:
    if channel in {
        RetrievalChannel.PATTERN_MASK,
        RetrievalChannel.PROTOTYPE_FULL_TERM,
        RetrievalChannel.PROTOTYPE_SEMANTIC_SKELETON,
    }:
        return query.prototype_source_identity_fingerprint
    return query.confirmed_source_identity_fingerprint


def _typed_tuple(value: object, expected: type[object]) -> bool:
    return isinstance(value, tuple) and all(isinstance(item, expected) for item in value)


def _is_hash(value: object) -> bool:
    return isinstance(value, str) and _HASH.fullmatch(value) is not None


def _positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _micros(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= SCORE_SCALE


def _tokens(values: object) -> bool:
    return (
        isinstance(values, tuple)
        and all(isinstance(value, str) and _TOKEN.fullmatch(value) for value in values)
        and values == tuple(sorted(set(values)))
    )


def _bad(code: str) -> None:
    raise HybridSourceError(code)
