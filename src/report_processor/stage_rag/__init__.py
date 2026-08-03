"""Optional deterministic semantic stage-relation suggestions (StageRelationRAG-18.0)."""

from .contracts import (
    DENSE_RETRIEVER_CONTRACT_VERSION,
    EMBEDDING_PROVIDER_CONTRACT_VERSION,
    VECTOR_STORE_CONTRACT_VERSION,
    DenseRetriever,
    EmbeddingProvider,
    StageEncoderEmbeddingProvider,
    VectorStore,
)
from .encoder import (
    EMBEDDING_DIMENSIONS,
    RUBERT_TINY2_MODEL_ID,
    RUBERT_TINY2_MODEL_REVISION,
    RuBERTTiny2Encoder,
    StageEncoder,
)
from .errors import (
    StageRAGError,
    StageRAGInputError,
    StageRAGModelUnavailableError,
    StageRAGStoreError,
    StageRAGStoreUnavailableError,
)
from .evaluation import DenseRAGEvaluation, evaluate_cases, evaluate_fixture
from .indexing import (
    CollectionReindexPlan,
    ConfirmedExampleIndexer,
    ConfirmedReviewOutcome,
    normalized_text_hash,
    plan_reindex,
    stable_example_id,
)
from .models import (
    STAGE_RELATION_RAG_CONTRACT_VERSION,
    ConfirmedExampleVector,
    DenseQuery,
    DenseRetrievalCandidate,
    DenseRetrievalQuery,
    DenseRetrievalResult,
    StageRelationCandidate,
    StageRelationSuggestion,
    StageText,
)
from .qdrant_store import InMemoryVectorStore, QdrantVectorStore
from .retrieval import StageRelationRAG, StoreBackedDenseRetriever, retrieve_stage_relations

__all__ = [
    "DENSE_RETRIEVER_CONTRACT_VERSION",
    "EMBEDDING_DIMENSIONS",
    "EMBEDDING_PROVIDER_CONTRACT_VERSION",
    "RUBERT_TINY2_MODEL_ID",
    "RUBERT_TINY2_MODEL_REVISION",
    "STAGE_RELATION_RAG_CONTRACT_VERSION",
    "VECTOR_STORE_CONTRACT_VERSION",
    "CollectionReindexPlan",
    "ConfirmedExampleIndexer",
    "ConfirmedExampleVector",
    "ConfirmedReviewOutcome",
    "DenseQuery",
    "DenseRAGEvaluation",
    "DenseRetrievalCandidate",
    "DenseRetrievalQuery",
    "DenseRetrievalResult",
    "DenseRetriever",
    "EmbeddingProvider",
    "InMemoryVectorStore",
    "QdrantVectorStore",
    "RuBERTTiny2Encoder",
    "StageEncoder",
    "StageEncoderEmbeddingProvider",
    "StageRAGError",
    "StageRAGInputError",
    "StageRAGModelUnavailableError",
    "StageRAGStoreError",
    "StageRAGStoreUnavailableError",
    "StageRelationCandidate",
    "StageRelationRAG",
    "StageRelationSuggestion",
    "StageText",
    "StoreBackedDenseRetriever",
    "VectorStore",
    "evaluate_cases",
    "evaluate_fixture",
    "normalized_text_hash",
    "plan_reindex",
    "retrieve_stage_relations",
    "stable_example_id",
]
