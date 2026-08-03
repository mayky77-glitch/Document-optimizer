"""Observed retrieval evaluation using real StoreBackedDenseRetriever boundaries."""

from __future__ import annotations

from pathlib import Path

import pytest

from report_processor.stage_rag.evaluation import (
    EvaluationQuery,
    evaluate_fixture,
    evaluate_queries,
)
from report_processor.stage_rag.models import (
    ConfirmedExampleVector,
    DenseRetrievalCandidate,
    DenseRetrievalQuery,
    DenseRetrievalResult,
)
from report_processor.stage_rag.qdrant_store import InMemoryVectorStore
from report_processor.stage_rag.retrieval import StoreBackedDenseRetriever


class DeterministicEmbeddingProvider:
    model_id = "test-model"
    revision = "test-revision"
    dimensions = 2

    def encode(self, texts):
        vectors = {
            "sanitized cable query": (1.0, 0.0),
            "sanitized concrete query": (0.0, 1.0),
        }
        return tuple(vectors[text] for text in texts)


def _example(example_id: str, vector: tuple[float, float]) -> ConfirmedExampleVector:
    return ConfirmedExampleVector(
        example_id=example_id,
        tenant_id="tenant-a",
        vector=vector,
        normalized_text_hash="a" * 64,
        embedding_model_id="test-model",
        embedding_model_revision="test-revision",
        taxonomy_version="taxonomy-1",
        review_decision="confirmed",
        project_id="project-7",
        document_type="visr",
    )


def _retriever() -> StoreBackedDenseRetriever:
    store = InMemoryVectorStore()
    store.upsert((_example("example-cable", (1.0, 0.0)), _example("example-concrete", (0.0, 1.0))))
    return StoreBackedDenseRetriever(DeterministicEmbeddingProvider(), store)


def test_sanitized_fixture_measures_actual_retrieval_and_binds_identity() -> None:
    ticks = iter((10.0, 10.001, 20.0, 20.003))

    result = evaluate_fixture(
        Path("tests/fixtures/stage_rag/dense_rag_evaluation.json"),
        _retriever(),
        clock=lambda: next(ticks),
    )

    assert result.query_count == 2
    assert result.recall_at_5 == result.mrr == 1.0
    assert result.top1_error_rate == 0.0
    assert result.review_rate == 1.0
    assert result.mean_latency_ms == pytest.approx(2.0)
    assert (result.model_id, result.model_revision) == ("test-model", "test-revision")
    assert result.index_identity == "in-memory-confirmed-examples"


def test_invalid_fixture_does_not_accept_fabricated_candidates_or_latency(tmp_path: Path) -> None:
    fixture = tmp_path / "invalid.json"
    fixture.write_text(
        '{"queries":[{"query_text":"x","expected_example_id":"id","tenant_id":"t","document_type":"d","taxonomy_version":"v","candidate_example_ids":["id"]}]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="недопустимые"):
        evaluate_fixture(fixture, _retriever())


def test_mixed_retriever_identity_is_rejected_when_result_identity_is_unavailable() -> None:
    class MixedRetriever:
        def __init__(self) -> None:
            self.calls = 0

        def retrieve(self, tenant_id, _text, *, limit, project_id, document_type, taxonomy_version):
            self.calls += 1
            self.index_identity = f"index-{self.calls}"
            return DenseRetrievalResult(
                query=DenseRetrievalQuery(
                    tenant_id=tenant_id,
                    vector=(1.0,),
                    embedding_model_id="test-model",
                    embedding_model_revision="test-revision",
                    embedding_dimensions=1,
                    limit=limit,
                    project_id=project_id,
                    document_type=document_type,
                    taxonomy_version=taxonomy_version,
                ),
                candidates=(DenseRetrievalCandidate("expected", 1.0),),
            )

    query = EvaluationQuery("sanitized", "expected", "tenant-a", None, "visr", "taxonomy-1")
    with pytest.raises(ValueError, match="смешанную"):
        evaluate_queries(MixedRetriever(), (query, query))


def test_context_mismatch_is_rejected_before_metrics() -> None:
    class WrongContextRetriever:
        def retrieve(self, tenant_id, _text, *, limit, project_id, document_type, taxonomy_version):
            return DenseRetrievalResult(
                query=DenseRetrievalQuery(
                    tenant_id="other-tenant",
                    vector=(1.0,),
                    embedding_model_id="test-model",
                    embedding_model_revision="test-revision",
                    embedding_dimensions=1,
                    limit=limit,
                    project_id=project_id,
                    document_type=document_type,
                    taxonomy_version=taxonomy_version,
                ),
                candidates=(),
            )

    query = EvaluationQuery("sanitized", "expected", "tenant-a", None, "visr", "taxonomy-1")
    with pytest.raises(ValueError, match="evaluation context"):
        evaluate_queries(WrongContextRetriever(), (query,))
