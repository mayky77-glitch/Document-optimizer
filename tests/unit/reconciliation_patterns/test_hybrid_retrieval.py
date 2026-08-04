"""Counterexamples for the recovered source-free hybrid retrieval contract."""

from __future__ import annotations

import dataclasses
import hashlib
from fractions import Fraction

import pytest

from report_processor.reconciliation_patterns import hybrid_retrieval as h
from report_processor.reconciliation_patterns.offline import OutcomeSignature
from report_processor.reconciliation_patterns.pattern_models import PatternVersions
from report_processor.reconciliation_patterns.pattern_registry import (
    DecisionSource,
    PatternDecision,
)


def _hash(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


def _query(*, exact_only: bool = False, limit: int = 10) -> h.HybridQuery:
    return h.create_hybrid_query(
        query_ref=_hash("query"),
        tenant_ref=_hash("tenant"),
        project_ref=_hash("project"),
        document_type_fingerprint=_hash("document"),
        taxonomy_version_fingerprint=_hash("taxonomy"),
        scope_fingerprint=_hash("scope"),
        consequential_version_fingerprint=_hash("version"),
        embedding_identity_fingerprint=_hash("embedding"),
        confirmed_source_identity_fingerprint=_hash("confirmed-index"),
        prototype_source_identity_fingerprint=_hash("prototype-index"),
        hard_negative_identity_fingerprint=_hash("negative-index"),
        full_term_fingerprint=_hash("term"),
        skeleton_fingerprint=_hash("skeleton"),
        exact_only=exact_only,
        limit=limit,
    )


def _versions() -> PatternVersions:
    return PatternVersions("Parser-1.0", "Model-1.0", "Taxonomy-1.0")


def _manual(query: h.HybridQuery) -> h.AuthorityEnvelope:
    return h.resolve_authority(
        query,
        exact_feedback=None,
        exact_feedback_ref=None,
        matched_histories=(),
        current_versions=_versions(),
    )


def _exact_authority(query: h.HybridQuery) -> h.AuthorityEnvelope:
    return h.resolve_authority(
        query,
        exact_feedback=OutcomeSignature("accept", "quantity_cost", "category"),
        exact_feedback_ref=_hash("feedback"),
        matched_histories=(),
        current_versions=_versions(),
    )


def _evidence(
    query: h.HybridQuery,
    *,
    name: str = "one",
    kind: h.EvidenceKind = h.EvidenceKind.CONFIRMED_EXAMPLE,
    full: str | None = None,
    **changes: object,
) -> h.HybridEvidence:
    prototype = kind is h.EvidenceKind.ACTIVE_PATTERN_PROTOTYPE
    values: dict[str, object] = dict(
        evidence_ref=_hash(f"evidence-{name}"),
        semantic_identity_fingerprint=_hash(f"identity-{name}"),
        kind=kind,
        pattern_id=_hash(f"pattern-{name}") if prototype else None,
        outcome=OutcomeSignature("accept", "quantity_cost", "category"),
        tenant_ref=query.tenant_ref,
        project_ref=query.project_ref,
        document_type_fingerprint=query.document_type_fingerprint,
        taxonomy_version_fingerprint=query.taxonomy_version_fingerprint,
        scope_fingerprint=query.scope_fingerprint,
        consequential_version_fingerprint=query.consequential_version_fingerprint,
        embedding_identity_fingerprint=query.embedding_identity_fingerprint,
        full_term_fingerprint=full or query.full_term_fingerprint,
        confirmed=True,
        unit_compatible=True,
        critical_slots_compatible=True,
        replay_fingerprint=_hash(f"replay-{name}") if prototype else None,
        owner_approval_ref=_hash(f"owner-{name}") if prototype else None,
        activation_fingerprint=_hash(f"activation-{name}") if prototype else None,
        contradiction_count=0,
        supporting_refs=(_hash(f"support-{name}"),),
        matched_slot_kinds=(),
        difference_codes=(),
    )
    values.update(changes)
    return h.create_hybrid_evidence(**values)


def _signal(
    query: h.HybridQuery,
    evidence: h.HybridEvidence,
    channel: h.RetrievalChannel,
    *,
    rank: int = 1,
    representation: h.RepresentationKind | None = None,
    similarity: int = 900_000,
) -> h.RankedSignal:
    rep = representation or {
        h.RetrievalChannel.PATTERN_MASK: h.RepresentationKind.SEMANTIC_SKELETON,
        h.RetrievalChannel.DENSE_SEMANTIC_SKELETON: h.RepresentationKind.SEMANTIC_SKELETON,
    }.get(channel, h.RepresentationKind.FULL_TERM)
    return h.create_ranked_signal(
        channel=channel,
        representation=rep,
        evidence_ref=evidence.evidence_ref,
        rank=rank,
        similarity_micros=similarity,
        index_identity_fingerprint=(
            query.prototype_source_identity_fingerprint
            if channel
            in {
                h.RetrievalChannel.PATTERN_MASK,
                h.RetrievalChannel.PROTOTYPE_FULL_TERM,
                h.RetrievalChannel.PROTOTYPE_SEMANTIC_SKELETON,
            }
            else query.confirmed_source_identity_fingerprint
        ),
    )


def _batches(
    query: h.HybridQuery,
    channel: h.RetrievalChannel = h.RetrievalChannel.LEXICAL,
    *signals: h.RankedSignal,
) -> tuple[h.SignalBatch, ...]:
    return tuple(
        h.create_signal_batch(
            query_fingerprint=query.fingerprint,
            channel=item,
            signals=signals if item is channel else (),
            unavailable=False,
            source_identity_fingerprint=(
                query.prototype_source_identity_fingerprint
                if item
                in {
                    h.RetrievalChannel.PATTERN_MASK,
                    h.RetrievalChannel.PROTOTYPE_FULL_TERM,
                    h.RetrievalChannel.PROTOTYPE_SEMANTIC_SKELETON,
                }
                else query.confirmed_source_identity_fingerprint
            ),
        )
        for item in sorted(h.RetrievalChannel, key=lambda x: x.value)
    )


def _negative_batch(
    query: h.HybridQuery, *hits: h.HardNegativeHit, unavailable: bool = False
) -> h.HardNegativeBatch:
    return h.create_hard_negative_batch(
        query_fingerprint=query.fingerprint,
        hits=hits,
        unavailable=unavailable,
        source_identity_fingerprint=query.hard_negative_identity_fingerprint,
    )


def _run(
    query: h.HybridQuery,
    evidence: tuple[h.HybridEvidence, ...],
    batches: tuple[h.SignalBatch, ...],
    negatives: h.HardNegativeBatch | None = None,
    authority: h.AuthorityEnvelope | None = None,
) -> h.HybridRetrievalResult:
    return h.rank_hybrid(
        query,
        authority=authority or _manual(query),
        evidence=evidence,
        batches=batches,
        hard_negative_batch=negatives or _negative_batch(query),
    )


def _hit(
    query: h.HybridQuery,
    evidence: h.HybridEvidence,
    *,
    name: str = "one",
    direct: bool = False,
    representation: h.RepresentationKind = h.RepresentationKind.FULL_TERM,
    similarity: int = 900_000,
) -> h.HardNegativeHit:
    return h.create_hard_negative_hit(
        query_fingerprint=query.fingerprint,
        positive_identity_fingerprint=evidence.semantic_identity_fingerprint,
        negative_ref=_hash(f"negative-{name}"),
        source_pattern_id=None,
        target_pattern_id=None,
        edge_fingerprint=_hash(f"edge-{name}"),
        representation=representation,
        rank=1,
        similarity_micros=similarity,
        direct_cannot_link=direct,
        scope_fingerprint=query.scope_fingerprint,
        consequential_version_fingerprint=query.consequential_version_fingerprint,
        difference_codes=(),
    )


def test_authority_is_query_bound_and_bare_decision_cannot_auto_accept() -> None:
    query = _query()
    evidence = _evidence(query)
    exact = PatternDecision(
        OutcomeSignature("accept", "quantity_cost", "category"), DecisionSource.EXACT_FEEDBACK, ()
    )
    envelope = _exact_authority(query)
    result = _run(query, (evidence,), _batches(query), authority=envelope)
    assert result.status is h.HybridStatus.AUTHORITATIVE_EXACT and not result.auto_accepted
    with pytest.raises(h.HybridRetrievalError):
        h.rank_hybrid(
            query,
            authority=exact,
            evidence=(),
            batches=(),
            hard_negative_batch=_negative_batch(query),
        )  # type: ignore[arg-type]


def test_strict_refs_tokens_bounds_and_tamper_fail_privately() -> None:
    query = _query()
    with pytest.raises(h.HybridRetrievalError):
        _query(limit=101)
    with pytest.raises(h.HybridRetrievalError):
        h.create_hybrid_query(
            query_ref="https://host/path",
            tenant_ref=_hash("t"),
            project_ref=None,
            document_type_fingerprint=_hash("d"),
            taxonomy_version_fingerprint=_hash("x"),
            scope_fingerprint=_hash("s"),
            consequential_version_fingerprint=_hash("v"),
            embedding_identity_fingerprint=_hash("e"),
            confirmed_source_identity_fingerprint=_hash("c"),
            prototype_source_identity_fingerprint=_hash("p"),
            hard_negative_identity_fingerprint=_hash("n"),
            full_term_fingerprint=_hash("f"),
            skeleton_fingerprint=_hash("k"),
            exact_only=False,
            limit=1,
        )
    with pytest.raises(h.HybridRetrievalError) as error:
        dataclasses.replace(query, fingerprint=_hash("tamper"))
    assert error.value.code == "FINGERPRINT_MISMATCH" and "tamper" not in str(error.value)


def test_complete_matrix_context_and_canonical_ranks_fail_closed() -> None:
    query = _query()
    evidence = _evidence(query)
    signal = _signal(query, evidence, h.RetrievalChannel.LEXICAL)
    assert _run(query, (evidence,), _batches(query, h.RetrievalChannel.LEXICAL, signal)).candidates
    wrong = _signal(
        query,
        evidence,
        h.RetrievalChannel.LEXICAL,
        representation=h.RepresentationKind.SEMANTIC_SKELETON,
    )
    assert (
        _run(query, (evidence,), _batches(query, h.RetrievalChannel.LEXICAL, wrong)).status
        is h.HybridStatus.UNAVAILABLE
    )
    foreign = _evidence(query, tenant_ref=_hash("foreign"))
    assert (
        _run(
            query,
            (foreign,),
            _batches(
                query,
                h.RetrievalChannel.LEXICAL,
                _signal(query, foreign, h.RetrievalChannel.LEXICAL),
            ),
        ).status
        is h.HybridStatus.UNAVAILABLE
    )
    rank_two = _signal(query, evidence, h.RetrievalChannel.LEXICAL, rank=2)
    assert (
        _run(query, (evidence,), _batches(query, h.RetrievalChannel.LEXICAL, rank_two)).status
        is h.HybridStatus.UNAVAILABLE
    )


def test_prototype_lifecycle_and_exact_only_proof() -> None:
    query = _query(exact_only=True)
    matching = _evidence(query)
    assert _run(
        query,
        (matching,),
        _batches(
            query, h.RetrievalChannel.LEXICAL, _signal(query, matching, h.RetrievalChannel.LEXICAL)
        ),
    ).candidates
    foreign = _evidence(query, name="other", full=_hash("other-term"))
    assert not _run(
        query,
        (foreign,),
        _batches(
            query, h.RetrievalChannel.LEXICAL, _signal(query, foreign, h.RetrievalChannel.LEXICAL)
        ),
    ).candidates
    with pytest.raises(h.HybridRetrievalError):
        _evidence(
            query,
            name="prototype",
            kind=h.EvidenceKind.ACTIVE_PATTERN_PROTOTYPE,
            activation_fingerprint=None,
        )


def test_rrf_hard_negative_direction_and_same_representation_margin() -> None:
    query = _query()
    evidence = _evidence(query)
    lexical = _signal(query, evidence, h.RetrievalChannel.LEXICAL, similarity=800_000)
    dense = _signal(query, evidence, h.RetrievalChannel.DENSE_FULL_TERM, similarity=700_000)
    batches = list(_batches(query, h.RetrievalChannel.LEXICAL, lexical))
    index = next(
        i for i, x in enumerate(batches) if x.channel is h.RetrievalChannel.DENSE_FULL_TERM
    )
    batches[index] = h.create_signal_batch(
        query_fingerprint=query.fingerprint,
        channel=h.RetrievalChannel.DENSE_FULL_TERM,
        signals=(dense,),
        unavailable=False,
        source_identity_fingerprint=query.confirmed_source_identity_fingerprint,
    )
    result = _run(query, (evidence,), tuple(batches))
    expected = Fraction(1, 61) + Fraction(1, 61)
    assert (result.candidates[0].score.numerator, result.candidates[0].score.denominator) == (
        expected.numerator,
        expected.denominator,
    )
    direct = _run(
        query,
        (evidence,),
        _batches(query, h.RetrievalChannel.LEXICAL, lexical),
        _negative_batch(query, _hit(query, evidence, direct=True)),
    )
    assert direct.candidates == ()  # confirmed evidence has no pattern ID, still excluded
    reverse = _run(
        query,
        (evidence,),
        _batches(query, h.RetrievalChannel.LEXICAL, lexical),
        _negative_batch(
            query,
            _hit(
                query,
                evidence,
                representation=h.RepresentationKind.SEMANTIC_SKELETON,
                similarity=900_000,
            ),
        ),
    )
    assert (
        h.ReasonCode.HARD_NEGATIVE_NEARER_OR_EQUAL
        not in reverse.candidates[0].explanation.reason_codes
    )


def test_missing_negative_source_and_result_forgery_fail_closed() -> None:
    query = _query()
    evidence = _evidence(query)
    batches = _batches(
        query, h.RetrievalChannel.LEXICAL, _signal(query, evidence, h.RetrievalChannel.LEXICAL)
    )
    assert (
        _run(query, (evidence,), batches, _negative_batch(query, unavailable=True)).status
        is h.HybridStatus.UNAVAILABLE
    )
    result = _run(query, (evidence,), batches)
    with pytest.raises(h.HybridRetrievalError):
        dataclasses.replace(result, auto_accepted=True)


def test_hard_negative_batch_rejects_exact_reverse_of_public_canonical_order() -> None:
    query = _query()
    evidence = _evidence(query)
    hits = (_hit(query, evidence, name="z"), _hit(query, evidence, name="a"))
    canonical = tuple(
        sorted(
            hits,
            key=lambda item: (
                item.positive_identity_fingerprint,
                item.rank,
                -item.similarity_micros,
                item.negative_ref,
                item.fingerprint,
            ),
        )
    )
    reverse = tuple(reversed(canonical))
    assert reverse != canonical
    h.create_hard_negative_batch(
        query_fingerprint=query.fingerprint,
        hits=canonical,
        unavailable=False,
        source_identity_fingerprint=query.hard_negative_identity_fingerprint,
    )
    with pytest.raises(h.HybridRetrievalError) as error:
        h.create_hard_negative_batch(
            query_fingerprint=query.fingerprint,
            hits=reverse,
            unavailable=False,
            source_identity_fingerprint=query.hard_negative_identity_fingerprint,
        )
    assert error.value.code == "INVALID_SCHEMA"


def test_two_negative_refs_are_retained_and_cross_bound_to_the_explanation() -> None:
    query = _query()
    evidence = _evidence(query)
    hits = tuple(
        sorted(
            (_hit(query, evidence, name="a"), _hit(query, evidence, name="b")),
            key=lambda x: x.negative_ref,
        )
    )
    result = _run(
        query,
        (evidence,),
        _batches(
            query, h.RetrievalChannel.LEXICAL, _signal(query, evidence, h.RetrievalChannel.LEXICAL)
        ),
        _negative_batch(query, *hits),
    )
    assert result.status is h.HybridStatus.REVIEW_REQUIRED
    assert len(result.candidates) == 1
    assert (
        h.ReasonCode.HARD_NEGATIVE_NEARER_OR_EQUAL in result.candidates[0].explanation.reason_codes
    )
    assert (
        {item.negative_ref for item in result.hard_negatives}
        == set(result.candidates[0].explanation.hard_negative_refs)
        == {item.negative_ref for item in hits}
    )
    assert result.requires_manual_review is True and result.auto_accepted is False


def test_mixed_type_hard_negative_codes_fail_privately_through_public_factory() -> None:
    query = _query()
    evidence = _evidence(query)
    with pytest.raises(h.HybridRetrievalError) as error:
        h.create_hard_negative_hit(
            query_fingerprint=query.fingerprint,
            positive_identity_fingerprint=evidence.semantic_identity_fingerprint,
            negative_ref=_hash("negative-mixed"),
            source_pattern_id=None,
            target_pattern_id=None,
            edge_fingerprint=_hash("edge-mixed"),
            representation=h.RepresentationKind.FULL_TERM,
            rank=1,
            similarity_micros=1,
            direct_cannot_link=False,
            scope_fingerprint=query.scope_fingerprint,
            consequential_version_fingerprint=query.consequential_version_fingerprint,
            difference_codes=("safe_code", 1),  # type: ignore[arg-type]
        )
    assert error.value.code == "INVALID_SCHEMA" and "safe_code" not in str(error.value)


def test_direct_dto_rejects_boolean_rank() -> None:
    query = _query()
    evidence = _evidence(query)
    candidate = _run(
        query,
        (evidence,),
        _batches(
            query, h.RetrievalChannel.LEXICAL, _signal(query, evidence, h.RetrievalChannel.LEXICAL)
        ),
    ).candidates[0]
    values = {
        field.name: getattr(candidate, field.name)
        for field in dataclasses.fields(candidate)
        if field.name not in {"fingerprint", "version"}
    }
    with pytest.raises(h.HybridRetrievalError):
        h.create_ranked_hybrid_candidate(**(values | {"rank": True}))


def test_direct_dto_rejects_boolean_channel_count() -> None:
    query = _query()
    evidence = _evidence(query)
    candidate = _run(
        query,
        (evidence,),
        _batches(
            query, h.RetrievalChannel.LEXICAL, _signal(query, evidence, h.RetrievalChannel.LEXICAL)
        ),
    ).candidates[0]
    values = {
        field.name: getattr(candidate, field.name)
        for field in dataclasses.fields(candidate)
        if field.name not in {"fingerprint", "version"}
    }
    with pytest.raises(h.HybridRetrievalError):
        h.create_ranked_hybrid_candidate(**(values | {"channel_count": True}))


def test_authoritative_results_retain_resolved_authority_and_reject_payload_artifacts() -> None:
    query = _query()
    authority = _exact_authority(query)
    ranked = _run(query, (), _batches(query), authority=authority)
    assert ranked.authority == authority
    assert ranked.candidates == ranked.hard_negatives == ranked.unavailable_channels == ()
    assert ranked.auto_accepted is False
    evidence = _evidence(query)
    assistive = _run(
        query,
        (evidence,),
        _batches(
            query, h.RetrievalChannel.LEXICAL, _signal(query, evidence, h.RetrievalChannel.LEXICAL)
        ),
    )
    authoritative = h.create_hybrid_retrieval_result(
        query_fingerprint=query.fingerprint,
        status=h.HybridStatus.AUTHORITATIVE_EXACT,
        authority=authority,
        candidates=(),
        hard_negatives=(),
        unavailable_channels=(),
        requires_manual_review=False,
        auto_accepted=False,
    )
    assert authoritative.authority == authority
    payload = {
        "query_fingerprint": query.fingerprint,
        "status": h.HybridStatus.AUTHORITATIVE_EXACT,
        "authority": authority,
        "candidates": (),
        "hard_negatives": (),
        "unavailable_channels": (),
        "requires_manual_review": False,
        "auto_accepted": False,
    }
    for field, value in (
        ("candidates", assistive.candidates),
        ("hard_negatives", (_hit(query, evidence),)),
        ("unavailable_channels", (h.RetrievalChannel.LEXICAL,)),
        ("query_fingerprint", _hash("wrong-query")),
        ("status", h.HybridStatus.AUTHORITATIVE_PATTERN),
    ):
        with pytest.raises(h.HybridRetrievalError) as error:
            h.create_hybrid_retrieval_result(**(payload | {field: value}))
        assert error.value.code == "INVALID_SCHEMA"


def test_signal_batch_rejects_reverse_of_two_valid_contiguous_signals() -> None:
    query = _query()
    first = _evidence(query, name="signal-first")
    second = _evidence(query, name="signal-second")
    rank_one = _signal(query, first, h.RetrievalChannel.LEXICAL, rank=1)
    rank_two = _signal(query, second, h.RetrievalChannel.LEXICAL, rank=2)
    canonical = (rank_one, rank_two)
    reverse = (rank_two, rank_one)
    assert reverse != canonical
    canonical_batch = h.create_signal_batch(
        query_fingerprint=query.fingerprint,
        channel=h.RetrievalChannel.LEXICAL,
        signals=canonical,
        unavailable=False,
        source_identity_fingerprint=query.confirmed_source_identity_fingerprint,
    )
    assert canonical_batch.signals == canonical
    with pytest.raises(h.HybridRetrievalError) as error:
        h.create_signal_batch(
            query_fingerprint=query.fingerprint,
            channel=h.RetrievalChannel.LEXICAL,
            signals=reverse,
            unavailable=False,
            source_identity_fingerprint=query.confirmed_source_identity_fingerprint,
        )
    assert error.value.code == "INVALID_SCHEMA"


def test_direct_result_rejects_101_unique_sorted_contiguous_candidates() -> None:
    query = _query()
    seed = _evidence(query)
    candidate = _run(
        query,
        (seed,),
        _batches(
            query, h.RetrievalChannel.LEXICAL, _signal(query, seed, h.RetrievalChannel.LEXICAL)
        ),
    ).candidates[0]
    candidates = tuple(
        h.create_ranked_hybrid_candidate(
            semantic_identity_fingerprint=_hash(f"identity-{index:03d}"),
            evidence_refs=(_hash(f"evidence-{index:03d}"),),
            outcome=candidate.outcome,
            score=candidate.score,
            channel_count=candidate.channel_count,
            rank=index + 1,
            explanation=h.create_hybrid_explanation(
                reason_codes=candidate.explanation.reason_codes,
                positive_refs=(_hash(f"evidence-{index:03d}"),),
                hard_negative_refs=(),
                matched_slot_kinds=(),
                difference_codes=(),
            ),
        )
        for index in range(101)
    )
    candidates = tuple(
        h.create_ranked_hybrid_candidate(
            semantic_identity_fingerprint=item.semantic_identity_fingerprint,
            evidence_refs=item.evidence_refs,
            outcome=item.outcome,
            score=item.score,
            channel_count=item.channel_count,
            rank=rank,
            explanation=item.explanation,
        )
        for rank, item in enumerate(
            sorted(candidates, key=lambda item: item.semantic_identity_fingerprint), start=1
        )
    )
    with pytest.raises(h.HybridRetrievalError) as error:
        h.create_hybrid_retrieval_result(
            query_fingerprint=query.fingerprint,
            status=h.HybridStatus.REVIEW_REQUIRED,
            authority=None,
            candidates=candidates,
            hard_negatives=(),
            unavailable_channels=(),
            requires_manual_review=True,
            auto_accepted=False,
        )
    assert error.value.code == "INVALID_SCHEMA"
