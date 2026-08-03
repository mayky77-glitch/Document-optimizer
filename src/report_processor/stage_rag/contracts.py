"""Public contracts for the tenant-isolated Dense RAG boundary."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .models import ConfirmedExampleVector, DenseRetrievalQuery, DenseRetrievalResult

EMBEDDING_PROVIDER_CONTRACT_VERSION = "EmbeddingProvider-1.0"
VECTOR_STORE_CONTRACT_VERSION = "VectorStore-1.0"
DENSE_RETRIEVER_CONTRACT_VERSION = "DenseRetriever-1.0"


class EmbeddingProvider(Protocol):
    """Produces one dense vector for every supplied input string."""

    def encode(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        """Encode the supplied texts without changing their order."""


class VectorStore(Protocol):
    """Stores confirmed examples and searches only within one tenant."""

    def upsert(self, examples: Sequence[ConfirmedExampleVector]) -> None:
        """Create or replace examples by their stable public ID."""

    def query(self, query: DenseRetrievalQuery) -> DenseRetrievalResult:
        """Return manual-review-only candidates for the query tenant."""


class DenseRetriever(Protocol):
    """Encodes a query and returns deterministic, filtered candidates."""

    def retrieve(self, query: DenseRetrievalQuery) -> DenseRetrievalResult:
        """Return a fail-safe result; candidates never auto-apply."""
