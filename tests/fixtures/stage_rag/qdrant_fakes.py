"""In-process VectorStore fake for indexer tests; it contains no source documents."""

from __future__ import annotations

from collections.abc import Sequence

from report_processor.stage_rag.models import (
    ConfirmedExampleVector,
    DenseRetrievalQuery,
    DenseRetrievalResult,
)


class RecordingVectorStore:
    def __init__(self) -> None:
        self.upserts: list[tuple[ConfirmedExampleVector, ...]] = []
        self.deactivations: list[tuple[str, tuple[str, ...]]] = []

    def upsert(self, examples: Sequence[ConfirmedExampleVector]) -> None:
        self.upserts.append(tuple(examples))

    def deactivate(self, tenant_id: str, example_ids: Sequence[str]) -> None:
        self.deactivations.append((tenant_id, tuple(example_ids)))

    def query(self, query: DenseRetrievalQuery) -> DenseRetrievalResult:
        return DenseRetrievalResult(query=query, candidates=())
