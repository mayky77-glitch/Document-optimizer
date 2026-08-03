"""Observed, reproducible Dense RAG evaluation over sanitized query corpora."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Protocol

from .models import DenseRetrievalResult


class DenseRetrieverBoundary(Protocol):
    """The real retrieval boundary observed by the evaluation harness."""

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
        """Return candidates for one explicitly scoped sanitized query."""


@dataclass(frozen=True, slots=True)
class EvaluationQuery:
    """Sanitized query text, expected public ID and mandatory isolation context."""

    query_text: str
    expected_example_id: str
    tenant_id: str
    project_id: str | None
    document_type: str
    taxonomy_version: str


@dataclass(frozen=True, slots=True)
class DenseRAGEvaluation:
    """Observed metrics bound to one model revision and immutable index identity."""

    query_count: int
    recall_at_5: float
    mrr: float
    top1_error_rate: float
    review_rate: float
    mean_latency_ms: float
    model_id: str
    model_revision: str
    index_identity: str


def evaluate_fixture(
    path: Path,
    retriever: DenseRetrieverBoundary,
    *,
    clock: Callable[[], float] = perf_counter,
) -> DenseRAGEvaluation:
    """Read a sanitized fixture and measure actual calls through DenseRetriever."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("queries"), list):
        raise ValueError("evaluation fixture должен содержать queries")
    queries = tuple(_parse_query(item) for item in payload["queries"])
    return evaluate_queries(retriever, queries, clock=clock)


def evaluate_queries(
    retriever: DenseRetrieverBoundary,
    queries: Sequence[EvaluationQuery],
    *,
    clock: Callable[[], float] = perf_counter,
) -> DenseRAGEvaluation:
    """Calculate metrics solely from observed retrieval results and measured elapsed time."""
    if not queries:
        raise ValueError("evaluation queries не должны быть пустыми")
    recalls = reciprocal_rank = top1_errors = reviews = 0
    latency_ms = 0.0
    observed_identity: tuple[str, str, str] | None = None
    for query in queries:
        started = clock()
        result = retriever.retrieve(
            query.tenant_id,
            query.query_text,
            limit=5,
            project_id=query.project_id,
            document_type=query.document_type,
            taxonomy_version=query.taxonomy_version,
        )
        elapsed = clock() - started
        if elapsed < 0:
            raise ValueError("clock не должен возвращать отрицательную latency")
        _validate_observed_result(result, query)
        identity = (
            result.query.embedding_model_id,
            result.query.embedding_model_revision,
            _observed_index_identity(result, retriever),
        )
        if observed_identity is not None and identity != observed_identity:
            raise ValueError("observed retrieval имеет смешанную model/index identity")
        observed_identity = identity
        candidate_ids = tuple(item.example_id for item in result.candidates[:5])
        if query.expected_example_id in candidate_ids:
            recalls += 1
            reciprocal_rank += 1 / (candidate_ids.index(query.expected_example_id) + 1)
        if not candidate_ids or candidate_ids[0] != query.expected_example_id:
            top1_errors += 1
        reviews += result.requires_manual_review
        latency_ms += elapsed * 1000
    assert observed_identity is not None
    count = len(queries)
    return DenseRAGEvaluation(
        query_count=count,
        recall_at_5=recalls / count,
        mrr=reciprocal_rank / count,
        top1_error_rate=top1_errors / count,
        review_rate=reviews / count,
        mean_latency_ms=latency_ms / count,
        model_id=observed_identity[0],
        model_revision=observed_identity[1],
        index_identity=observed_identity[2],
    )


def evaluate_cases(
    retriever: DenseRetrieverBoundary,
    queries: Sequence[EvaluationQuery],
    *,
    clock: Callable[[], float] = perf_counter,
) -> DenseRAGEvaluation:
    """Compatibility entry point that still evaluates only observed retrieval calls."""
    return evaluate_queries(retriever, queries, clock=clock)


def _parse_query(value: object) -> EvaluationQuery:
    if not isinstance(value, dict):
        raise ValueError("evaluation query должен быть object")
    forbidden = {"candidate_example_ids", "candidates", "latency_ms"}
    if forbidden.intersection(value):
        raise ValueError("evaluation query содержит недопустимые fabricated results")
    required = (
        "query_text",
        "expected_example_id",
        "tenant_id",
        "document_type",
        "taxonomy_version",
    )
    if any(not isinstance(value.get(key), str) or not value[key].strip() for key in required):
        raise ValueError("evaluation query имеет недопустимые поля")
    project_id = value.get("project_id")
    if project_id is not None and (not isinstance(project_id, str) or not project_id.strip()):
        raise ValueError("evaluation query имеет недопустимый project_id")
    return EvaluationQuery(
        query_text=value["query_text"],
        expected_example_id=value["expected_example_id"],
        tenant_id=value["tenant_id"],
        project_id=project_id,
        document_type=value["document_type"],
        taxonomy_version=value["taxonomy_version"],
    )


def _validate_observed_result(result: object, expected: EvaluationQuery) -> None:
    if not isinstance(result, DenseRetrievalResult):
        raise ValueError("retriever должен вернуть DenseRetrievalResult")
    query = result.query
    if (
        query.tenant_id != expected.tenant_id
        or query.project_id != expected.project_id
        or query.document_type != expected.document_type
        or query.taxonomy_version != expected.taxonomy_version
    ):
        raise ValueError("observed retrieval не совпадает с evaluation context")


def _observed_index_identity(result: DenseRetrievalResult, retriever: object) -> str:
    """Read immutable identity from the result when available, with legacy-boundary support."""
    identity = getattr(result, "index_identity", None)
    if not isinstance(identity, str) or not identity.strip() or identity == "unavailable":
        identity = getattr(retriever, "index_identity", None)
    if not isinstance(identity, str) or not identity.strip():
        store = getattr(retriever, "_vector_store", None)
        collection = getattr(store, "_collection_name", None)
        if isinstance(collection, str) and collection.strip():
            identity = f"qdrant:{collection}"
        elif store is not None and type(store).__name__ == "InMemoryVectorStore":
            identity = "in-memory-confirmed-examples"
    if not isinstance(identity, str) or not identity.strip():
        raise ValueError("observed retrieval не содержит index identity")
    return identity
