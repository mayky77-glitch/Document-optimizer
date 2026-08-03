"""Public Dense RAG contract checks independent of a live Qdrant instance."""

from __future__ import annotations

from report_processor.stage_rag.contracts import (
    DENSE_RETRIEVER_CONTRACT_VERSION,
    EMBEDDING_PROVIDER_CONTRACT_VERSION,
    VECTOR_STORE_CONTRACT_VERSION,
    StageEncoderEmbeddingProvider,
)
from report_processor.stage_rag.errors import StageRAGStoreUnavailableError
from report_processor.stage_rag.models import DenseRetrievalQuery, DenseRetrievalResult
from report_processor.stage_rag.retrieval import StoreBackedDenseRetriever


def test_dense_contract_versions_are_pinned() -> None:
    assert EMBEDDING_PROVIDER_CONTRACT_VERSION == "EmbeddingProvider-1.0"
    assert VECTOR_STORE_CONTRACT_VERSION == "VectorStore-1.0"
    assert DENSE_RETRIEVER_CONTRACT_VERSION == "DenseRetriever-1.0"


def test_retriever_returns_empty_manual_review_result_when_store_is_unavailable() -> None:
    class Encoder:
        model_id = "local-model"
        revision = "rev-1"
        dimensions = 2

        def encode(self, texts):
            return ((1.0, 0.0),)

    class OfflineStore:
        index_identity = "offline-test-store"

        def query(self, query: DenseRetrievalQuery):
            raise StageRAGStoreUnavailableError("unavailable")

    result = StoreBackedDenseRetriever(Encoder(), OfflineStore()).retrieve("tenant-a", "query")

    assert result.unavailable is True
    assert result.candidates == ()
    assert result.requires_manual_review is True
    assert result.auto_accepted is False
    assert result.index_identity == "offline-test-store"


def test_stage_encoder_adapter_exposes_required_embedding_metadata() -> None:
    class ExistingEncoder:
        def encode(self, texts):
            return ((1.0, 0.0),)

    provider = StageEncoderEmbeddingProvider(
        ExistingEncoder(), model_id="model", revision="revision", dimensions=2
    )

    assert (provider.model_id, provider.revision, provider.dimensions) == ("model", "revision", 2)
    assert provider.encode(("query",)) == ((1.0, 0.0),)


def test_dense_result_preserves_legacy_third_positional_unavailable_argument() -> None:
    query = DenseRetrievalQuery("tenant", (1.0,), "model", "revision", 1)
    result = DenseRetrievalResult(query, (), True, index_identity="index")

    assert result.unavailable is True
    assert result.index_identity == "index"
