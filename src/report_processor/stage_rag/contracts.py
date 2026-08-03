"""Public contracts for the tenant-isolated Dense RAG boundary."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .encoder import (
    EMBEDDING_DIMENSIONS,
    RUBERT_TINY2_MODEL_ID,
    RUBERT_TINY2_MODEL_REVISION,
    StageEncoder,
)
from .models import ConfirmedExampleVector, DenseRetrievalQuery, DenseRetrievalResult

EMBEDDING_PROVIDER_CONTRACT_VERSION = "EmbeddingProvider-1.0"
VECTOR_STORE_CONTRACT_VERSION = "VectorStore-1.0"
DENSE_RETRIEVER_CONTRACT_VERSION = "DenseRetriever-1.0"


class EmbeddingProvider(Protocol):
    """Produces one dense vector for every supplied input string."""

    model_id: str
    revision: str
    dimensions: int

    def encode(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        """Encode the supplied texts without changing their order."""


class VectorStore(Protocol):
    """Stores confirmed examples and searches only within one tenant."""

    @property
    def index_identity(self) -> str:
        """Immutable identity of the collection or local index serving results."""

    def upsert(self, examples: Sequence[ConfirmedExampleVector]) -> None:
        """Create or replace examples by their stable public ID."""

    def query(self, query: DenseRetrievalQuery) -> DenseRetrievalResult:
        """Return manual-review-only candidates for the query tenant."""

    def deactivate(self, tenant_id: str, example_ids: Sequence[str]) -> None:
        """Make explicit confirmed examples ineligible for future search."""


class DenseRetriever(Protocol):
    """Encodes a query and returns deterministic, filtered candidates."""

    def retrieve(
        self,
        tenant_id: str,
        text: str,
        *,
        limit: int = 5,
        project_id: str | None = None,
        document_type: str | None = None,
        taxonomy_version: str | None = None,
    ) -> DenseRetrievalResult:
        """Return a fail-safe result; candidates never auto-apply."""


class StageEncoderEmbeddingProvider:
    """Metadata-bearing adapter that keeps the existing StageEncoder usable."""

    def __init__(
        self,
        encoder: StageEncoder,
        *,
        model_id: str = RUBERT_TINY2_MODEL_ID,
        revision: str = RUBERT_TINY2_MODEL_REVISION,
        dimensions: int = EMBEDDING_DIMENSIONS,
    ) -> None:
        self._encoder = encoder
        self.model_id = model_id
        self.revision = revision
        self.dimensions = dimensions

    def encode(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        return self._encoder.encode(texts)
