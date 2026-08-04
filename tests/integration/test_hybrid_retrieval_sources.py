"""Executable acceptance gates for the inert HybridSources-1.0 adapter."""

from __future__ import annotations

import dataclasses
import hashlib
import importlib
import inspect
from collections.abc import Callable

import pytest

from report_processor.reconciliation_patterns import feedback_graph as graph
from report_processor.reconciliation_patterns import hybrid_retrieval as core
from report_processor.reconciliation_patterns import offline
from report_processor.reconciliation_patterns import pattern_models as models
from report_processor.reconciliation_patterns import pattern_registry as registry
from report_processor.stage_rag.models import (
    DenseRetrievalCandidate,
    DenseRetrievalQuery,
    DenseRetrievalResult,
)
from report_processor.work_semantics.semantic_skeleton import build_semantic_skeleton


def _hash(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


def _versions(model: str = "Model-1.0") -> models.PatternVersions:
    return models.PatternVersions("Parser-1.0", model, "Taxonomy-1.0")


@pytest.fixture
def sources():
    """The absent module keeps every gate red before production exists."""
    return importlib.import_module("report_processor.reconciliation_patterns.hybrid_sources")


def _query(**changes: object) -> core.HybridQuery:
    values: dict[str, object] = {
        "query_ref": _hash("query"),
        "tenant_ref": _hash("tenant"),
        "project_ref": _hash("project"),
        "document_type_fingerprint": _hash("document"),
        "taxonomy_version_fingerprint": _hash("taxonomy"),
        "scope_fingerprint": _hash("scope"),
        "consequential_version_fingerprint": _hash("versions"),
        "embedding_identity_fingerprint": _hash("embedding"),
        "confirmed_source_identity_fingerprint": _hash("confirmed-source"),
        "prototype_source_identity_fingerprint": _hash("prototype-source"),
        "hard_negative_identity_fingerprint": _hash("negative-source"),
        "full_term_fingerprint": _hash("full-term"),
        "skeleton_fingerprint": _hash("skeleton"),
        "exact_only": False,
        "limit": 10,
    }
    values.update(changes)
    return core.create_hybrid_query(**values)


def _authority(
    query: core.HybridQuery,
    *,
    exact: bool = False,
    histories: tuple[registry.RegistryHistory, ...] = (),
    versions: models.PatternVersions | None = None,
) -> core.AuthorityEnvelope:
    return core.resolve_authority(
        query,
        exact_feedback=(
            offline.OutcomeSignature("accept", "quantity_cost", "category") if exact else None
        ),
        exact_feedback_ref=_hash("feedback") if exact else None,
        matched_histories=histories,
        current_versions=versions or _versions(),
    )


def _candidate(name: str, *, category: str = "category") -> offline.PatternCandidate:
    scope = offline.PatternScope(category, "quantity_cost", "unit", "accept", "object", "doc")
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
        2,
        2,
        2,
        2,
        0,
        tuple(sorted((_hash(name + "-a"), _hash(name + "-b")))),
    )
    return offline.PatternCandidate(
        "candidate",
        candidate_id,
        offline.CandidateKind.INCLUDE_EXCLUDE,
        scope,
        proposal,
        offline.OutcomeSignature("accept", "quantity_cost", category),
        support,
        (),
        offline.fingerprint({"candidate_id": candidate_id, "support": support, "risks": ()}),
    )


def _active_history(name: str, *, category: str = "category") -> registry.RegistryHistory:
    history = registry.register_candidate(
        _candidate(name, category=category), versions=_versions(), actor_ref=_hash("miner")
    )
    history = registry.move_to_shadow(
        history, expected_head=history.head, actor_ref=_hash("shadow")
    )
    history = registry.approve_head(
        history,
        expected_head=history.head,
        owner_ref=_hash("owner-" + name),
        approval_ref=_hash("approval-" + name),
    )
    return registry.import_verified_wave5_active(
        history,
        expected_head=history.head,
        activation=models.ActivationMetadata(
            _hash("activation-" + name),
            _hash("activation-fingerprint-" + name),
            4,
            _hash("wave5-" + name),
        ),
        actor_ref=_hash("wave5-import"),
    )


def _evidence(
    query: core.HybridQuery,
    *,
    name: str,
    prototype_history: registry.RegistryHistory | None = None,
    **changes: object,
) -> core.HybridEvidence:
    prototype = prototype_history is not None
    values: dict[str, object] = {
        "evidence_ref": _hash("evidence-" + name),
        "semantic_identity_fingerprint": _hash("identity-" + name),
        "kind": (
            core.EvidenceKind.ACTIVE_PATTERN_PROTOTYPE
            if prototype
            else core.EvidenceKind.CONFIRMED_EXAMPLE
        ),
        "pattern_id": prototype_history.head.pattern_id if prototype else None,
        "outcome": offline.OutcomeSignature("accept", "quantity_cost", "category"),
        "tenant_ref": query.tenant_ref,
        "project_ref": query.project_ref,
        "document_type_fingerprint": query.document_type_fingerprint,
        "taxonomy_version_fingerprint": query.taxonomy_version_fingerprint,
        "scope_fingerprint": query.scope_fingerprint,
        "consequential_version_fingerprint": query.consequential_version_fingerprint,
        "embedding_identity_fingerprint": query.embedding_identity_fingerprint,
        "full_term_fingerprint": query.full_term_fingerprint,
        "confirmed": True,
        "unit_compatible": True,
        "critical_slots_compatible": True,
        "replay_fingerprint": _hash("replay-" + name) if prototype else None,
        "owner_approval_ref": (prototype_history.head.owner.approval_ref if prototype else None),
        "activation_fingerprint": (
            prototype_history.head.activation.activation_fingerprint if prototype else None
        ),
        "contradiction_count": 0,
        "supporting_refs": (_hash("support-" + name),),
        "matched_slot_kinds": ("diameter",),
        "difference_codes": (),
    }
    values.update(changes)
    return core.create_hybrid_evidence(**values)


class _Binder:
    def __init__(self, mapping: dict[tuple[str, str | None], str | None]) -> None:
        self.mapping = mapping
        self.calls: list[tuple[str, str | None]] = []

    def bind(self, namespace: str, value: str | None) -> str | None:
        self.calls.append((namespace, value))
        return self.mapping.get((namespace, value))


class _RankedSource:
    def __init__(
        self,
        index_identity: str,
        values: tuple[object, ...] = (),
        error: Exception | None = None,
    ) -> None:
        self.index_identity = index_identity
        self.values = values
        self.error = error
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def retrieve(self, *args: object, **kwargs: object) -> tuple[object, ...]:
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        return self.values


class _DenseSource:
    def __init__(
        self,
        index_identity: str,
        resolver: Callable[[str], DenseRetrievalResult],
        error: Exception | None = None,
    ) -> None:
        self.index_identity = index_identity
        self.resolver = resolver
        self.error = error
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def retrieve(self, *args: object, **kwargs: object) -> DenseRetrievalResult:
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        text = args[1] if len(args) > 1 else kwargs.get("text")
        assert isinstance(text, str)
        return self.resolver(text)


class _HardNegativeSource:
    def __init__(
        self,
        index_identity: str,
        values: tuple[object, ...] = (),
        error: Exception | None = None,
    ) -> None:
        self.index_identity = index_identity
        self.values = values
        self.error = error
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def retrieve(self, *args: object, **kwargs: object) -> tuple[object, ...]:
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        return self.values


def _dense_result(
    text: str,
    *,
    index_identity: str,
    candidate_ids: tuple[str, ...] = (),
    candidates: tuple[DenseRetrievalCandidate, ...] | None = None,
    unavailable: bool = False,
) -> DenseRetrievalResult:
    query = DenseRetrievalQuery(
        tenant_id="tenant",
        vector=(1.0,),
        embedding_model_id="model",
        embedding_model_revision="revision",
        embedding_dimensions=1,
        limit=10,
        project_id="project",
        document_type="document",
        taxonomy_version="taxonomy",
    )
    resolved_candidates = candidates or tuple(
        DenseRetrievalCandidate(value, 0.9 - index * 0.1, "category", "confirmed", "taxonomy")
        for index, value in enumerate(candidate_ids)
    )
    return DenseRetrievalResult(
        query,
        resolved_candidates,
        unavailable=unavailable,
        index_identity=index_identity,
    )


def _empty_graph() -> graph.FeedbackGraph:
    return graph.create_feedback_graph(edges=())


def _binder(
    query: core.HybridQuery,
    *,
    term: str,
    skeleton: str,
    confirmed_ids: dict[str, str] | None = None,
    prototype_ids: dict[str, str] | None = None,
    overrides: dict[tuple[str, str | None], str | None] | None = None,
) -> _Binder:
    mapping: dict[tuple[str, str | None], str | None] = {
        ("tenant_ref", "tenant"): query.tenant_ref,
        ("project_ref", "project"): query.project_ref,
        ("document_type_fingerprint", "document"): query.document_type_fingerprint,
        ("taxonomy_version_fingerprint", "taxonomy"): query.taxonomy_version_fingerprint,
        ("full_term_fingerprint", term): query.full_term_fingerprint,
        ("skeleton_fingerprint", skeleton): query.skeleton_fingerprint,
        (
            "embedding_identity_fingerprint",
            "model|revision|1",
        ): query.embedding_identity_fingerprint,
        (
            "confirmed_source_identity_fingerprint",
            "confirmed-index",
        ): query.confirmed_source_identity_fingerprint,
        (
            "prototype_source_identity_fingerprint",
            "prototype-index",
        ): query.prototype_source_identity_fingerprint,
        (
            "hard_negative_identity_fingerprint",
            "negative-index",
        ): query.hard_negative_identity_fingerprint,
    }
    mapping.update(
        (("confirmed_evidence_ref", source_id), evidence_ref)
        for source_id, evidence_ref in (confirmed_ids or {}).items()
    )
    mapping.update(
        (("prototype_evidence_ref", source_id), evidence_ref)
        for source_id, evidence_ref in (prototype_ids or {}).items()
    )
    mapping.update(overrides or {})
    return _Binder(mapping)


def _setup(
    sources,
    *,
    term: str = "труба 25 мм",
    exact: bool = False,
    histories: tuple[registry.RegistryHistory, ...] = (),
    authority_histories: tuple[registry.RegistryHistory, ...] = (),
    confirmed: tuple[core.HybridEvidence, ...] = (),
    prototypes: tuple[core.HybridEvidence, ...] = (),
    pattern_values: tuple[object, ...] = (),
    lexical_values: tuple[object, ...] = (),
    confirmed_ids: tuple[str, ...] = (),
    prototype_ids: tuple[str, ...] = (),
    hard_values: tuple[object, ...] = (),
    graph_value: graph.FeedbackGraph | None = None,
) -> tuple[core.HybridQuery, dict[str, object]]:
    query = _query()
    skeleton = build_semantic_skeleton(
        term, category="category", object_kind="object"
    ).skeleton_text
    binder = _binder(
        query,
        term=term,
        skeleton=skeleton,
        confirmed_ids={
            source_id: evidence.evidence_ref
            for source_id, evidence in zip(confirmed_ids, confirmed, strict=False)
        },
        prototype_ids={
            source_id: evidence.evidence_ref
            for source_id, evidence in zip(prototype_ids, prototypes, strict=False)
        },
    )
    confirmed_dense = _DenseSource(
        "confirmed-index",
        lambda text: _dense_result(
            text, index_identity="confirmed-index", candidate_ids=confirmed_ids
        ),
    )
    prototype_dense = _DenseSource(
        "prototype-index",
        lambda text: _dense_result(
            text, index_identity="prototype-index", candidate_ids=prototype_ids
        ),
    )
    values: dict[str, object] = {
        "authority": _authority(query, exact=exact, histories=authority_histories),
        "normalized_term": term,
        "tenant_id": "tenant",
        "project_id": "project",
        "document_type": "document",
        "taxonomy_version": "taxonomy",
        "category": "category",
        "object_kind": "object",
        "binder": binder,
        "current_versions": _versions(),
        "confirmed_evidence": confirmed,
        "prototype_evidence": prototypes,
        "prototype_histories": histories,
        "feedback_graph": graph_value or _empty_graph(),
        "pattern_mask_source": _RankedSource("prototype-index", pattern_values),
        "lexical_source": _RankedSource("confirmed-index", lexical_values),
        "confirmed_dense_source": confirmed_dense,
        "prototype_dense_source": prototype_dense,
        "hard_negative_source": _HardNegativeSource("negative-index", hard_values),
    }
    return query, values


def _collect(sources, query: core.HybridQuery, values: dict[str, object]):
    return sources.collect_hybrid_sources(query, **values)


def test_public_surface_is_small_frozen_and_transient(sources) -> None:
    assert sources.HYBRID_SOURCES_VERSION == "HybridSources-1.0"
    assert tuple(inspect.signature(sources.collect_hybrid_sources).parameters) == (
        "query",
        "authority",
        "normalized_term",
        "tenant_id",
        "project_id",
        "document_type",
        "taxonomy_version",
        "category",
        "object_kind",
        "binder",
        "current_versions",
        "confirmed_evidence",
        "prototype_evidence",
        "prototype_histories",
        "feedback_graph",
        "pattern_mask_source",
        "lexical_source",
        "confirmed_dense_source",
        "prototype_dense_source",
        "hard_negative_source",
    )
    assert {field.name for field in dataclasses.fields(sources.SourceMatch)} == {
        "evidence_ref",
        "rank",
        "similarity_micros",
    }
    assert {field.name for field in dataclasses.fields(sources.HardNegativeMatch)} == {
        "positive_identity_fingerprint",
        "negative_ref",
        "source_pattern_id",
        "target_pattern_id",
        "edge_fingerprint",
        "representation",
        "rank",
        "similarity_micros",
        "difference_codes",
    }
    assert {field.name for field in dataclasses.fields(sources.HybridSourceBundle)} == {
        "batches",
        "hard_negative_batch",
        "fingerprint",
        "version",
    }
    for name in ("SourceMatch", "HardNegativeMatch", "HybridSourceBundle"):
        value = getattr(sources, name)
        assert value.__dataclass_params__.frozen and "__slots__" in vars(value)
    for name in ("OpaqueBinder", "RankedSource", "DenseSource", "HardNegativeSource"):
        assert getattr(sources, name)._is_protocol


@pytest.mark.parametrize("authority_kind", ("exact", "conflict"))
def test_authority_short_circuits_every_source(sources, authority_kind: str) -> None:
    histories: tuple[registry.RegistryHistory, ...] = ()
    if authority_kind == "conflict":
        histories = (
            _active_history("left", category="category"),
            _active_history("right", category="other"),
        )
    query, values = _setup(
        sources,
        exact=authority_kind == "exact",
        histories=histories,
        authority_histories=histories,
    )
    bundle = _collect(sources, query, values)
    assert len(bundle.batches) == len(core.RetrievalChannel)
    assert all(batch.unavailable and batch.signals == () for batch in bundle.batches)
    assert bundle.hard_negative_batch.unavailable
    for key in (
        "pattern_mask_source",
        "lexical_source",
        "confirmed_dense_source",
        "prototype_dense_source",
        "hard_negative_source",
    ):
        assert not values[key].calls


def test_manual_happy_path_populates_all_six_channels_and_core_can_rank(sources) -> None:
    query = _query()
    history = _active_history("prototype")
    confirmed = _evidence(query, name="confirmed")
    prototype = _evidence(query, name="prototype", prototype_history=history)
    pattern = sources.SourceMatch(prototype.evidence_ref, 1, 820_000)
    lexical = sources.SourceMatch(confirmed.evidence_ref, 1, 830_000)
    query, values = _setup(
        sources,
        histories=(history,),
        confirmed=(confirmed,),
        prototypes=(prototype,),
        pattern_values=(pattern,),
        lexical_values=(lexical,),
        confirmed_ids=("confirmed-raw-id",),
        prototype_ids=("prototype-raw-id",),
    )
    values["authority"] = _authority(query)
    bundle = _collect(sources, query, values)
    assert tuple(batch.channel for batch in bundle.batches) == tuple(
        sorted(core.RetrievalChannel, key=lambda item: item.value)
    )
    assert all(not batch.unavailable and len(batch.signals) == 1 for batch in bundle.batches)
    result = core.rank_hybrid(
        query,
        authority=values["authority"],
        evidence=(confirmed, prototype),
        batches=bundle.batches,
        hard_negative_batch=bundle.hard_negative_batch,
    )
    assert result.status is core.HybridStatus.REVIEW_REQUIRED
    assert result.candidates and not result.auto_accepted and result.requires_manual_review


def test_permutation_is_deterministic_and_batches_are_canonical(sources) -> None:
    query = _query()
    first = _evidence(query, name="a")
    second = _evidence(query, name="b")
    matches = (
        sources.SourceMatch(second.evidence_ref, 2, 700_000),
        sources.SourceMatch(first.evidence_ref, 1, 800_000),
    )
    query, values = _setup(
        sources,
        confirmed=(second, first),
        lexical_values=matches,
    )
    one = _collect(sources, query, values)
    values["confirmed_evidence"] = (first, second)
    values["lexical_source"].values = tuple(reversed(matches))
    two = _collect(sources, query, values)
    assert one == two
    lexical = next(batch for batch in one.batches if batch.channel is core.RetrievalChannel.LEXICAL)
    assert tuple(signal.rank for signal in lexical.signals) == (1, 2)


def test_bound_context_mismatch_suppresses_all_source_calls(sources) -> None:
    query, values = _setup(sources)
    values["binder"].mapping[("tenant_ref", "tenant")] = _hash("foreign")
    bundle = _collect(sources, query, values)
    assert all(batch.unavailable for batch in bundle.batches)
    assert bundle.hard_negative_batch.unavailable
    for key in (
        "pattern_mask_source",
        "lexical_source",
        "confirmed_dense_source",
        "prototype_dense_source",
        "hard_negative_source",
    ):
        assert not values[key].calls


def test_one_source_failure_is_isolated_and_backend_text_never_escapes(sources) -> None:
    query, values = _setup(sources, term="secret/path.xlsx")
    values["pattern_mask_source"] = _RankedSource(
        "prototype-index", error=RuntimeError("https://backend/private")
    )
    bundle = _collect(sources, query, values)
    by_channel = {batch.channel: batch for batch in bundle.batches}
    assert by_channel[core.RetrievalChannel.PATTERN_MASK].unavailable
    assert all(
        not batch.unavailable
        for channel, batch in by_channel.items()
        if channel is not core.RetrievalChannel.PATTERN_MASK
    )
    material = repr(bundle).lower()
    assert "secret" not in material and "backend" not in material and "http" not in material


def test_dense_source_identity_mismatch_isolates_its_two_channels(sources) -> None:
    query, values = _setup(sources)
    dense_identity = "foreign-confirmed-dense-index"
    values["confirmed_dense_source"].index_identity = dense_identity
    values["binder"].mapping[("confirmed_source_identity_fingerprint", dense_identity)] = _hash(
        "wrong-source"
    )
    bundle = _collect(sources, query, values)
    by_channel = {batch.channel: batch for batch in bundle.batches}
    assert by_channel[core.RetrievalChannel.DENSE_FULL_TERM].unavailable
    assert by_channel[core.RetrievalChannel.DENSE_SEMANTIC_SKELETON].unavailable
    assert not by_channel[core.RetrievalChannel.LEXICAL].unavailable
    assert not by_channel[core.RetrievalChannel.PROTOTYPE_FULL_TERM].unavailable
    assert not values["confirmed_dense_source"].calls
    assert values["lexical_source"].calls


@pytest.mark.parametrize(
    ("review_decision", "taxonomy_version", "candidate_category"),
    (
        ("pending", "taxonomy", "category"),
        ("confirmed", "foreign-taxonomy", "category"),
        ("confirmed", "taxonomy", "foreign-category"),
    ),
)
def test_dense_candidate_metadata_mismatch_makes_only_dense_batches_unavailable(
    sources,
    review_decision: str,
    taxonomy_version: str,
    candidate_category: str,
) -> None:
    initial_query = _query()
    confirmed = _evidence(initial_query, name="confirmed")
    lexical = sources.SourceMatch(confirmed.evidence_ref, 1, 800_000)
    query, values = _setup(
        sources,
        confirmed=(confirmed,),
        lexical_values=(lexical,),
        confirmed_ids=("confirmed-raw-id",),
    )
    values["confirmed_dense_source"] = _DenseSource(
        "confirmed-index",
        lambda text: _dense_result(
            text,
            index_identity="confirmed-index",
            candidates=(
                DenseRetrievalCandidate(
                    "confirmed-raw-id",
                    0.9,
                    candidate_category,
                    review_decision,
                    taxonomy_version,
                ),
            ),
        ),
    )

    bundle = _collect(sources, query, values)

    by_channel = {batch.channel: batch for batch in bundle.batches}
    unavailable = {
        core.RetrievalChannel.DENSE_FULL_TERM,
        core.RetrievalChannel.DENSE_SEMANTIC_SKELETON,
    }
    assert all(by_channel[channel].unavailable for channel in unavailable)
    assert all(
        not batch.unavailable for channel, batch in by_channel.items() if channel not in unavailable
    )
    assert len(values["confirmed_dense_source"].calls) == 2


def test_full_term_and_skeleton_are_queried_separately(sources) -> None:
    term = "труба 25 мм"
    query, values = _setup(sources, term=term)
    bundle = _collect(sources, query, values)
    assert len(values["confirmed_dense_source"].calls) == 2
    texts = {call[0][1] for call in values["confirmed_dense_source"].calls}
    skeleton = build_semantic_skeleton(term, category="category", object_kind="object")
    assert texts == {term, skeleton.skeleton_text}
    by_channel = {batch.channel: batch for batch in bundle.batches}
    assert not by_channel[core.RetrievalChannel.DENSE_FULL_TERM].unavailable
    assert not by_channel[core.RetrievalChannel.DENSE_SEMANTIC_SKELETON].unavailable


def test_prototype_requires_current_active_history_and_lifecycle(sources) -> None:
    query = _query()
    history = _active_history("prototype")
    prototype = _evidence(query, name="prototype", prototype_history=history)
    match = sources.SourceMatch(prototype.evidence_ref, 1, 800_000)
    query, values = _setup(
        sources,
        histories=(history,),
        prototypes=(prototype,),
        pattern_values=(match,),
        prototype_ids=("prototype-raw-id",),
    )
    values["current_versions"] = _versions("Model-2.0")
    bundle = _collect(sources, query, values)
    by_channel = {batch.channel: batch for batch in bundle.batches}
    assert by_channel[core.RetrievalChannel.PATTERN_MASK].unavailable
    assert by_channel[core.RetrievalChannel.PROTOTYPE_FULL_TERM].unavailable
    assert by_channel[core.RetrievalChannel.PROTOTYPE_SEMANTIC_SKELETON].unavailable
    assert not by_channel[core.RetrievalChannel.LEXICAL].unavailable


def _provenance(
    source: models.FeedbackEndpoint, target: models.FeedbackEndpoint
) -> models.FeedbackProvenance:
    confirmations = tuple(
        sorted(
            (
                models.FeedbackConfirmation(
                    _hash("confirm-source"),
                    _hash("document-source"),
                    _hash("apply-source"),
                    _hash("result-source"),
                    source.outcome,
                ),
                models.FeedbackConfirmation(
                    _hash("confirm-target"),
                    _hash("document-target"),
                    _hash("apply-target"),
                    _hash("result-target"),
                    target.outcome,
                ),
            ),
            key=lambda item: item.confirmation_ref,
        )
    )
    return models.FeedbackProvenance(
        confirmations,
        tuple(sorted(item.document_set_ref for item in confirmations)),
        tuple(sorted(item.apply_fingerprint for item in confirmations)),
        tuple(sorted(item.result_fingerprint for item in confirmations)),
    )


def _hard_negative_graph() -> tuple[graph.FeedbackGraph, models.FeedbackEdge]:
    source_record = registry.register_candidate(
        _candidate("source"), versions=_versions(), actor_ref=_hash("miner")
    ).head
    target_record = registry.register_candidate(
        _candidate("target", category="other"),
        versions=_versions(),
        actor_ref=_hash("miner"),
    ).head
    source = models.FeedbackEndpoint(
        source_record.pattern_id, source_record.candidate_id, source_record.expected_outcome
    )
    target = models.FeedbackEndpoint(
        target_record.pattern_id, target_record.candidate_id, target_record.expected_outcome
    )
    edge = graph.create_explicit_edge(
        relation=models.FeedbackRelation.HARD_NEGATIVE,
        reason=models.FeedbackReason.EXPLICIT_AUTHORITATIVE_CONFLICT,
        source=source,
        target=target,
        provenance=_provenance(source, target),
    )
    return graph.create_feedback_graph(edges=(edge,)), edge


def test_hard_negative_direction_is_attested_by_real_feedback_graph(sources) -> None:
    query = _query()
    positive = _evidence(query, name="positive")
    graph_value, edge = _hard_negative_graph()
    direct = sources.HardNegativeMatch(
        positive.semantic_identity_fingerprint,
        _hash("negative"),
        edge.source.pattern_id,
        edge.target.pattern_id,
        edge.fingerprint,
        core.RepresentationKind.FULL_TERM,
        1,
        900_000,
        ("category_conflict",),
    )
    query, values = _setup(
        sources,
        confirmed=(positive,),
        hard_values=(direct,),
        graph_value=graph_value,
    )
    bundle = _collect(sources, query, values)
    assert len(bundle.hard_negative_batch.hits) == 1
    assert bundle.hard_negative_batch.hits[0].direct_cannot_link
    reverse = dataclasses.replace(
        direct,
        source_pattern_id=edge.target.pattern_id,
        target_pattern_id=edge.source.pattern_id,
    )
    values["hard_negative_source"].values = (reverse,)
    reversed_bundle = _collect(sources, query, values)
    assert reversed_bundle.hard_negative_batch.hits == ()
    assert not reversed_bundle.hard_negative_batch.unavailable


def test_hard_negative_failure_is_required_unavailable_but_positive_sources_survive(
    sources,
) -> None:
    query, values = _setup(sources)
    values["hard_negative_source"] = _HardNegativeSource(
        "negative-index", error=RuntimeError("/private/provider.log")
    )
    bundle = _collect(sources, query, values)
    assert bundle.hard_negative_batch.unavailable
    assert all(not batch.unavailable for batch in bundle.batches)
    assert "private" not in repr(bundle).lower() and "provider" not in repr(bundle).lower()


def test_adapter_is_read_only_manual_and_has_no_runtime_side_effects(sources) -> None:
    query, values = _setup(sources)
    bundle = _collect(sources, query, values)
    result = core.rank_hybrid(
        query,
        authority=values["authority"],
        evidence=(),
        batches=bundle.batches,
        hard_negative_batch=bundle.hard_negative_batch,
    )
    assert result.auto_accepted is False and result.requires_manual_review is True
    assert not hasattr(bundle, "decision")
    assert not hasattr(bundle, "persist")
    assert not hasattr(bundle, "apply")
    assert all(
        len(values[name].calls) in {1, 2}
        for name in (
            "pattern_mask_source",
            "lexical_source",
            "confirmed_dense_source",
            "prototype_dense_source",
            "hard_negative_source",
        )
    )
