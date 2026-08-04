"""Public schema lock for HybridRetrieval-1.0 remediation."""

from __future__ import annotations

import dataclasses
import inspect

from report_processor.reconciliation_patterns import hybrid_retrieval as hybrid


def test_frozen_models_include_query_bound_authority_and_negative_batch() -> None:
    assert (hybrid.HYBRID_RETRIEVAL_VERSION, hybrid.RRF_K, hybrid.SCORE_SCALE) == (
        "HybridRetrieval-1.0",
        60,
        1_000_000,
    )
    assert {item.value for item in hybrid.ReasonCode} == {
        "exact_feedback_applied",
        "active_pattern_applied",
        "pattern_conflict",
        "pattern_mask_match",
        "lexical_match",
        "dense_full_term_match",
        "dense_semantic_skeleton_match",
        "prototype_full_term_match",
        "prototype_semantic_skeleton_match",
        "slot_match",
        "hard_negative_nearer_or_equal",
        "forbidden_hard_negative",
        "exact_only",
        "source_unavailable",
        "manual_review_required",
    }
    fields = {
        name: {field.name for field in dataclasses.fields(getattr(hybrid, name))}
        for name in (
            "HybridQuery",
            "AuthorityEnvelope",
            "HybridEvidence",
            "RankedSignal",
            "SignalBatch",
            "HardNegativeHit",
            "HardNegativeBatch",
            "RationalScore",
            "HybridExplanation",
            "RankedHybridCandidate",
            "HybridRetrievalResult",
        )
    }
    assert "hard_negative_identity_fingerprint" in fields["HybridQuery"]
    assert {
        "confirmed_source_identity_fingerprint",
        "prototype_source_identity_fingerprint",
    } <= fields["HybridQuery"]
    assert "create_authority_envelope" not in vars(hybrid)
    assert "resolve_authority" in vars(hybrid)
    assert not any(
        name.startswith("_") and name.endswith("build") for name in vars(hybrid.AuthorityEnvelope)
    )
    assert fields["AuthorityEnvelope"] == {
        "query_fingerprint",
        "decision",
        "exact_feedback_ref",
        "active_pattern_ids",
        "active_head_fingerprints",
        "consequential_version_fingerprint",
        "fingerprint",
        "version",
    }
    assert "direct_cannot_link" in fields["HardNegativeHit"]
    assert fields["HardNegativeBatch"] == {
        "query_fingerprint",
        "hits",
        "unavailable",
        "source_identity_fingerprint",
        "fingerprint",
        "version",
    }
    assert "authority" in fields["HybridRetrievalResult"]
    for name in fields:
        model = getattr(hybrid, name)
        assert model.__dataclass_params__.frozen
        assert "__slots__" in vars(model)


def test_rank_boundary_requires_envelope_and_required_negative_batch() -> None:
    signature = inspect.signature(hybrid.rank_hybrid)
    assert tuple(signature.parameters) == (
        "query",
        "authority",
        "evidence",
        "batches",
        "hard_negative_batch",
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for name, parameter in signature.parameters.items()
        if name != "query"
    )
