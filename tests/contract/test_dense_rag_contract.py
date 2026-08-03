"""Public Dense RAG contract checks independent of a live Qdrant instance."""

from __future__ import annotations

from report_processor.stage_rag.contracts import (
    DENSE_RETRIEVER_CONTRACT_VERSION,
    EMBEDDING_PROVIDER_CONTRACT_VERSION,
    VECTOR_STORE_CONTRACT_VERSION,
)
from report_processor.stage_rag.errors import StageRAGStoreUnavailableError
from report_processor.stage_rag.models import DenseRetrievalQuery
from report_processor.stage_rag.retrieval import StoreBackedDenseRetriever


def test_dense_contract_versions_are_pinned() -> None:
    assert EMBEDDING_PROVIDER_CONTRACT_VERSION == "EmbeddingProvider-1.0"
    assert VECTOR_STORE_CONTRACT_VERSION == "VectorStore-1.0"
    assert DENSE_RETRIEVER_CONTRACT_VERSION == "DenseRetriever-1.0"


def test_retriever_returns_empty_manual_review_result_when_store_is_unavailable() -> None:
    class Encoder:
        def encode(self, texts):
            return ((1.0, 0.0),)

    class OfflineStore:
        def query(self, query: DenseRetrievalQuery):
            raise StageRAGStoreUnavailableError("unavailable")

    result = StoreBackedDenseRetriever(Encoder(), OfflineStore()).retrieve("tenant-a", "query")

    assert result.unavailable is True
    assert result.candidates == ()
    assert result.requires_manual_review is True
    assert result.auto_accepted is False
