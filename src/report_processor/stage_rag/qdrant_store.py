"""Dependency-free Qdrant REST and deterministic in-memory vector stores."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .errors import StageRAGInputError, StageRAGStoreError, StageRAGStoreUnavailableError
from .models import (
    ConfirmedExampleVector,
    DenseRetrievalCandidate,
    DenseRetrievalQuery,
    DenseRetrievalResult,
)


class InMemoryVectorStore:
    """Small deterministic fallback intended for tests and local development."""

    def __init__(self) -> None:
        self._examples: dict[str, ConfirmedExampleVector] = {}

    def upsert(self, examples: Sequence[ConfirmedExampleVector]) -> None:
        for example in examples:
            if not isinstance(example, ConfirmedExampleVector):
                raise StageRAGInputError(
                    "INVALID_EXAMPLE", "examples должен содержать ConfirmedExampleVector"
                )
            self._examples[example.example_id] = example

    def query(self, query: DenseRetrievalQuery) -> DenseRetrievalResult:
        candidates = []
        for example in self._examples.values():
            if not _matches(example, query):
                continue
            candidates.append(_candidate_from_example(example, _dot(query.vector, example.vector)))
        return DenseRetrievalResult(query=query, candidates=tuple(_rank(candidates)[: query.limit]))

    def search(self, query: DenseRetrievalQuery) -> DenseRetrievalResult:
        """Compatibility spelling for a filtered vector query."""
        return self.query(query)


class QdrantVectorStore:
    """Qdrant v1.18 REST adapter with a non-optional tenant must-filter."""

    def __init__(
        self,
        base_url: str,
        collection_name: str,
        *,
        api_key: str | None = None,
        timeout_seconds: float = 2.0,
    ) -> None:
        if not isinstance(base_url, str) or not base_url.startswith(("http://", "https://")):
            raise StageRAGInputError("INVALID_QDRANT_URL", "base_url должен быть HTTP(S) URL")
        if (
            not isinstance(collection_name, str)
            or not collection_name.strip()
            or "/" in collection_name
        ):
            raise StageRAGInputError("INVALID_COLLECTION", "collection_name недопустимо")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or timeout_seconds <= 0
        ):
            raise StageRAGInputError("INVALID_TIMEOUT", "timeout_seconds должен быть положительным")
        self._base_url = base_url.rstrip("/")
        self._collection_name = collection_name
        self._api_key = api_key
        self._timeout_seconds = float(timeout_seconds)

    def upsert(self, examples: Sequence[ConfirmedExampleVector]) -> None:
        points = []
        for example in examples:
            if not isinstance(example, ConfirmedExampleVector):
                raise StageRAGInputError(
                    "INVALID_EXAMPLE", "examples должен содержать ConfirmedExampleVector"
                )
            points.append(
                {
                    "id": example.example_id,
                    "vector": list(example.vector),
                    "payload": example.payload(),
                }
            )
        if points:
            self._request("PUT", "/points?wait=true", {"points": points})

    def query(self, query: DenseRetrievalQuery) -> DenseRetrievalResult:
        body: dict[str, Any] = {
            "query": list(query.vector),
            "limit": query.limit,
            "with_payload": True,
            "filter": {"must": [{"key": "tenant_id", "match": {"value": query.tenant_id}}]},
        }
        filters = (
            ("project_id", query.project_id),
            ("document_type", query.document_type),
            ("taxonomy_version", query.taxonomy_version),
        )
        for key, value in filters:
            if value is not None:
                body["filter"]["must"].append({"key": key, "match": {"value": value}})
        response = self._request("POST", "/points/query", body)
        raw_points = _response_points(response)
        candidates = []
        for point in raw_points:
            candidate = _candidate_from_qdrant_point(point, query)
            if candidate is not None:
                candidates.append(candidate)
        return DenseRetrievalResult(query=query, candidates=tuple(_rank(candidates)[: query.limit]))

    def search(self, query: DenseRetrievalQuery) -> DenseRetrievalResult:
        """Compatibility spelling for a filtered vector query."""
        return self.query(query)

    def _request(self, method: str, suffix: str, body: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["api-key"] = self._api_key
        request = Request(
            f"{self._base_url}/collections/{self._collection_name}{suffix}",
            data=json.dumps(body, separators=(",", ":")).encode(),
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                parsed = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            raise StageRAGStoreUnavailableError("Qdrant недоступен") from exc
        if not isinstance(parsed, dict):
            raise StageRAGStoreError("INVALID_QDRANT_RESPONSE", "Qdrant вернул некорректный ответ")
        return parsed


def _response_points(response: dict[str, Any]) -> Sequence[object]:
    result = response.get("result", {})
    points = result.get("points", ()) if isinstance(result, dict) else result
    if not isinstance(points, list):
        raise StageRAGStoreError("INVALID_QDRANT_RESPONSE", "Qdrant вернул некорректные points")
    return points


def _candidate_from_qdrant_point(
    point: object, query: DenseRetrievalQuery
) -> DenseRetrievalCandidate | None:
    if not isinstance(point, dict):
        return None
    payload = point.get("payload")
    score = point.get("score")
    if not isinstance(payload, dict) or not isinstance(score, (int, float)):
        return None
    if payload.get("tenant_id") != query.tenant_id:
        return None
    example_id = payload.get("example_id", point.get("id"))
    if not isinstance(example_id, str) or not example_id:
        return None
    return DenseRetrievalCandidate(
        example_id=example_id,
        score=float(score),
        category=_optional_string(payload.get("category")),
        review_decision=_optional_string(payload.get("review_decision")),
        taxonomy_version=_optional_string(payload.get("taxonomy_version")),
    )


def _matches(example: ConfirmedExampleVector, query: DenseRetrievalQuery) -> bool:
    return (
        example.tenant_id == query.tenant_id
        and (query.project_id is None or example.project_id == query.project_id)
        and (query.document_type is None or example.document_type == query.document_type)
        and (query.taxonomy_version is None or example.taxonomy_version == query.taxonomy_version)
    )


def _candidate_from_example(
    example: ConfirmedExampleVector, score: float
) -> DenseRetrievalCandidate:
    return DenseRetrievalCandidate(
        example.example_id,
        score,
        example.category,
        example.review_decision,
        example.taxonomy_version,
    )


def _rank(candidates: Sequence[DenseRetrievalCandidate]) -> list[DenseRetrievalCandidate]:
    return sorted(candidates, key=lambda item: (-item.score, item.example_id))


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
