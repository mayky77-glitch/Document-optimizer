"""Unit coverage for deterministic, manual-review-only StageRelationRAG retrieval."""

from __future__ import annotations

import math

import pytest

from fixtures.stage_rag.builders import FakeEncoder
from report_processor.stage_rag import (
    StageRAGInputError,
    StageRelationRAG,
    StageText,
    retrieve_stage_relations,
)


def _stage(identity: str) -> StageText:
    return StageText(identity, identity)


def test_normalized_cosine_scores_and_function_entry_point_match() -> None:
    encoder = FakeEncoder(
        {
            "source-x": (3, 4),
            "source-y": (0, 5),
            "target": (6, 8),
        }
    )
    sources = (_stage("source-y"), _stage("source-x"))
    targets = (_stage("target"),)

    direct = StageRelationRAG(encoder, embedding_dimensions=2).suggest(sources, targets, k=2)
    wrapped = retrieve_stage_relations(encoder, sources, targets, k=2, embedding_dimensions=2)

    assert direct == wrapped
    assert tuple(candidate.source_identity for candidate in direct[0].candidates) == (
        "source-x",
        "source-y",
    )
    assert tuple(candidate.score for candidate in direct[0].candidates) == pytest.approx((1.0, 0.8))


def test_ties_and_reversed_inputs_have_stable_identity_order() -> None:
    encoder = FakeEncoder(
        {
            "a": (1, 0),
            "b": (2, 0),
            "c": (0, 1),
            "target-a": (1, 0),
            "target-b": (0, 1),
        }
    )
    rag = StageRelationRAG(encoder, embedding_dimensions=2)
    sources = tuple(_stage(value) for value in ("b", "c", "a"))
    targets = tuple(_stage(value) for value in ("target-b", "target-a"))

    first = rag.suggest(sources, targets, k=3)
    second = rag.suggest(tuple(reversed(sources)), tuple(reversed(targets)), k=3)

    assert first == second
    assert tuple(item.target_identity for item in first) == ("target-a", "target-b")
    assert tuple(candidate.source_identity for candidate in first[0].candidates) == ("a", "b", "c")
    assert tuple(candidate.source_identity for candidate in first[1].candidates) == ("c", "a", "b")
    assert all(item.requires_manual_review and not item.auto_accepted for item in first)


def test_empty_inputs_are_deterministic_and_do_not_encode_unneeded_values() -> None:
    encoder = FakeEncoder({"target": (1, 0)})
    rag = StageRelationRAG(encoder, embedding_dimensions=2)

    assert rag.suggest((_stage("target"),), (), k=1) == ()
    assert encoder.calls == []
    assert rag.suggest((), (_stage("target"),), k=1)[0].candidates == ()
    assert encoder.calls == []


@pytest.mark.parametrize(
    ("vectors", "code"),
    [
        ({"source": (1,), "target": (1, 0)}, "INVALID_VECTOR_DIMENSION"),
        ({"source": (math.nan, 0), "target": (1, 0)}, "NONFINITE_VECTOR"),
        ({"source": (0, 0), "target": (1, 0)}, "ZERO_VECTOR"),
    ],
)
def test_invalid_vectors_are_rejected_with_controlled_codes(vectors, code: str) -> None:
    with pytest.raises(StageRAGInputError) as caught:
        StageRelationRAG(FakeEncoder(vectors), embedding_dimensions=2).suggest(
            (_stage("source"),), (_stage("target"),), k=1
        )
    assert caught.value.code == code


@pytest.mark.parametrize("k", (0, -1, 2, True, 1.0))
def test_invalid_k_is_rejected(k: object) -> None:
    rag = StageRelationRAG(
        FakeEncoder({"source": (1, 0), "target": (1, 0)}), embedding_dimensions=2
    )
    with pytest.raises(StageRAGInputError, match="INVALID_K"):
        rag.suggest((_stage("source"),), (_stage("target"),), k=k)  # type: ignore[arg-type]


def test_invalid_stage_identity_duplicate_and_encoder_failure_are_controlled() -> None:
    with pytest.raises(ValueError):
        StageText(" ", "text")
    rag = StageRelationRAG(FakeEncoder({"a": (1, 0), "target": (1, 0)}), embedding_dimensions=2)
    with pytest.raises(StageRAGInputError, match="DUPLICATE_IDENTITY"):
        rag.suggest((_stage("a"), _stage("a")), (_stage("target"),), k=1)

    class BrokenEncoder:
        def encode(self, texts):
            raise RuntimeError("offline")

    with pytest.raises(StageRAGInputError, match="ENCODER_FAILURE"):
        StageRelationRAG(BrokenEncoder(), embedding_dimensions=2).suggest(
            (_stage("a"),), (_stage("target"),), k=1
        )
