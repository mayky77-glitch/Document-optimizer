"""Semantic retrieval adapters that can only enrich manual review."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import TYPE_CHECKING

from report_processor.stage_rag import (
    RuBERTTiny2Encoder,
    StageRAGError,
    StageText,
    retrieve_stage_relations,
)
from report_processor.stage_rag.models import DenseRetrievalCandidate

from .examples import ConfirmedExample, RetrievedExample

if TYPE_CHECKING:
    from report_processor.stage_rag.contracts import DenseRetriever


MAX_DENSE_REVIEW_CANDIDATES = 5


@dataclass(frozen=True, slots=True)
class DenseRetrievalContext:
    """The explicit isolation context required for one drawing-card lookup."""

    tenant_id: str
    project_id: str | None
    document_type: str
    taxonomy_version: str

    def __post_init__(self) -> None:
        required = (self.tenant_id, self.document_type, self.taxonomy_version)
        if any(not isinstance(value, str) or not value.strip() for value in required):
            raise ValueError("Dense retrieval context requires tenant, document, and taxonomy")
        if self.project_id is not None and (
            not isinstance(self.project_id, str) or not self.project_id.strip()
        ):
            raise ValueError("Dense retrieval project must be a non-empty string when supplied")


@dataclass(frozen=True, slots=True)
class DenseSemanticSuggestion:
    """Bounded, opaque Dense RAG evidence for a manual decision."""

    candidates: tuple[DenseRetrievalCandidate, ...]
    unavailable: bool = False

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(item.example_id for item in self.candidates)

    @property
    def scores(self) -> tuple[float, ...]:
        return tuple(item.score for item in self.candidates)


class DenseSemanticRetriever:
    """Adapt a tenant-filtered DenseRetriever without exposing backend failures."""

    def __init__(self, retriever: DenseRetriever, context: DenseRetrievalContext) -> None:
        self._retriever = retriever
        self._context = context

    def search(self, text: str, *, top_k: int) -> DenseSemanticSuggestion:
        """Return only bounded candidate IDs/scores, or a controlled fallback."""
        try:
            result = self._retriever.retrieve(
                self._context.tenant_id,
                text,
                limit=min(max(top_k, 1), MAX_DENSE_REVIEW_CANDIDATES),
                project_id=self._context.project_id,
                document_type=self._context.document_type,
                taxonomy_version=self._context.taxonomy_version,
            )
            if result.unavailable or not self._query_matches_context(result.query):
                return DenseSemanticSuggestion((), unavailable=True)
            candidates = tuple(result.candidates[:MAX_DENSE_REVIEW_CANDIDATES])
        except Exception:
            return DenseSemanticSuggestion((), unavailable=True)
        return DenseSemanticSuggestion(candidates)

    def _query_matches_context(self, query: object) -> bool:
        return (
            getattr(query, "tenant_id", None) == self._context.tenant_id
            and getattr(query, "project_id", None) == self._context.project_id
            and getattr(query, "document_type", None) == self._context.document_type
            and getattr(query, "taxonomy_version", None) == self._context.taxonomy_version
        )


class SemanticExampleRetriever:
    """Retrieve confirmed examples from the pinned local model, never a network."""

    _encoder: RuBERTTiny2Encoder | None = None
    _encoder_lock = Lock()

    def __init__(self, examples: tuple[ConfirmedExample, ...]) -> None:
        self._examples = examples

    @classmethod
    def _shared_encoder(cls) -> RuBERTTiny2Encoder:
        with cls._encoder_lock:
            if cls._encoder is None:
                cls._encoder = RuBERTTiny2Encoder()
            return cls._encoder

    def search(self, text: str, *, top_k: int) -> tuple[RetrievedExample, ...]:
        if not self._examples:
            return ()
        sources = tuple(
            StageText(identity=example.example_id, text=example.normalized_text)
            for example in self._examples
        )
        try:
            suggestion = retrieve_stage_relations(
                self._shared_encoder(),
                sources,
                (StageText(identity="query", text=text),),
                k=min(top_k, len(sources)),
            )[0]
        except (StageRAGError, ValueError, TypeError):
            return ()
        by_id = {example.example_id: example for example in self._examples}
        return tuple(
            RetrievedExample(by_id[item.source_identity], item.score)
            for item in suggestion.candidates
        )
