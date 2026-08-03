"""Focused coverage for Qdrant REST tenant isolation and fallback storage."""

from __future__ import annotations

import json
from dataclasses import replace
from unittest.mock import patch
from urllib.error import URLError

import pytest

from report_processor.stage_rag.errors import StageRAGInputError, StageRAGStoreUnavailableError
from report_processor.stage_rag.models import ConfirmedExampleVector, DenseRetrievalQuery
from report_processor.stage_rag.qdrant_store import (
    InMemoryVectorStore,
    QdrantVectorStore,
    _qdrant_point_id,
)


def _example(example_id: str, tenant_id: str, vector: tuple[float, ...]) -> ConfirmedExampleVector:
    return ConfirmedExampleVector(
        example_id=example_id,
        tenant_id=tenant_id,
        vector=vector,
        normalized_text_hash="a" * 64,
        embedding_model_id="local-model",
        embedding_model_revision="rev-1",
        taxonomy_version="taxonomy-1",
        review_decision="confirmed",
        category="category",
    )


def _query(tenant_id: str, vector: tuple[float, ...], **kwargs: object) -> DenseRetrievalQuery:
    return DenseRetrievalQuery(
        tenant_id=tenant_id,
        vector=vector,
        embedding_model_id="local-model",
        embedding_model_revision="rev-1",
        embedding_dimensions=len(vector),
        **kwargs,
    )


def test_in_memory_store_filters_tenant_and_orders_score_then_public_example_id() -> None:
    store = InMemoryVectorStore()
    store.upsert(
        (
            _example("b", "tenant-a", (1.0, 0.0)),
            _example("a", "tenant-a", (1.0, 0.0)),
            _example("foreign", "tenant-b", (1.0, 0.0)),
        )
    )

    result = store.query(_query("tenant-a", (1.0, 0.0), limit=5))

    assert tuple(candidate.example_id for candidate in result.candidates) == ("a", "b")
    assert all(
        candidate.requires_manual_review and not candidate.auto_accepted
        for candidate in result.candidates
    )


def test_qdrant_query_uses_v118_endpoint_and_nonoptional_exact_tenant_must_filter() -> None:
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            payload = {
                "result": {
                    "points": [
                        {
                            "id": "b",
                            "score": 0.8,
                            "payload": {
                                "example_id": "b",
                                "tenant_id": "tenant-a",
                                "category": "B",
                                "embedding_model_id": "local-model",
                                "embedding_model_revision": "rev-1",
                                "embedding_dimensions": 2,
                                "active": True,
                            },
                        },
                        {
                            "id": "a",
                            "score": 0.8,
                            "payload": {
                                "example_id": "a",
                                "tenant_id": "tenant-a",
                                "category": "A",
                                "embedding_model_id": "local-model",
                                "embedding_model_revision": "rev-1",
                                "embedding_dimensions": 2,
                                "active": True,
                            },
                        },
                        {
                            "id": "foreign",
                            "score": 1,
                            "payload": {"example_id": "foreign", "tenant_id": "tenant-b"},
                        },
                    ]
                }
            }
            return json.dumps(payload).encode()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return Response()

    store = QdrantVectorStore(
        "http://qdrant.test/", "confirmed_examples_v1", api_key="test", timeout_seconds=1.5
    )
    with patch("report_processor.stage_rag.qdrant_store.urlopen", fake_urlopen):
        result = store.query(_query("tenant-a", (1.0, 0.0), project_id="p", document_type="spec"))

    assert captured["url"] == "http://qdrant.test/collections/confirmed_examples_v1/points/query"
    assert captured["timeout"] == 1.5
    assert captured["body"]["filter"]["must"] == [
        {"key": "tenant_id", "match": {"value": "tenant-a"}},
        {"key": "embedding_model_id", "match": {"value": "local-model"}},
        {"key": "embedding_model_revision", "match": {"value": "rev-1"}},
        {"key": "embedding_dimensions", "match": {"value": 2}},
        {"key": "active", "match": {"value": True}},
        {"key": "project_id", "match": {"value": "p"}},
        {"key": "document_type", "match": {"value": "spec"}},
    ]
    assert tuple(candidate.example_id for candidate in result.candidates) == ("a", "b")


def test_qdrant_transport_errors_are_controlled_without_response_body() -> None:
    store = QdrantVectorStore("http://qdrant.test", "confirmed_examples_v1")
    with (
        patch("report_processor.stage_rag.qdrant_store.urlopen", side_effect=URLError("offline")),
        pytest.raises(StageRAGStoreUnavailableError, match="Qdrant недоступен"),
    ):
        store.query(_query("tenant-a", (1.0,)))


def test_audit_reference_cannot_be_a_local_path() -> None:
    with pytest.raises(ValueError, match="audit_reference"):
        replace(_example("one", "tenant-a", (1.0,)), audit_reference="/private/book.xlsx")


def test_in_memory_store_uses_cosine_and_excludes_deactivated_examples() -> None:
    store = InMemoryVectorStore()
    store.upsert(
        (
            _example("high-dot-low-cosine", "tenant-a", (100.0, 100.0)),
            _example("cosine-one", "tenant-a", (1.0, 0.0)),
        )
    )

    candidates = store.query(_query("tenant-a", (1.0, 0.0))).candidates
    assert tuple(item.example_id for item in candidates) == (
        "cosine-one",
        "high-dot-low-cosine",
    )
    store.deactivate(("cosine-one",))
    candidates = store.query(_query("tenant-a", (1.0, 0.0))).candidates
    assert tuple(item.example_id for item in candidates) == ("high-dot-low-cosine",)


@pytest.mark.parametrize(
    ("vector", "code"),
    [((0.0, 0.0), "ZERO_VECTOR"), ((1.0,), "INVALID_VECTOR_DIMENSION")],
)
def test_in_memory_store_rejects_unsafe_query_vectors(vector: tuple[float, ...], code: str) -> None:
    store = InMemoryVectorStore()
    store.upsert((_example("example", "tenant-a", (1.0, 0.0)),))

    with pytest.raises(StageRAGInputError, match=code):
        store.query(_query("tenant-a", vector))


def test_qdrant_upsert_and_deactivate_use_deterministic_valid_uuid_point_ids() -> None:
    captured = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"result":{"operation_id":1}}'

    def fake_urlopen(request, timeout):
        captured.append((request.full_url, json.loads(request.data)))
        return Response()

    store = QdrantVectorStore("http://qdrant.test", "confirmed_examples_v1")
    with patch("report_processor.stage_rag.qdrant_store.urlopen", fake_urlopen):
        store.upsert((_example("public-id", "tenant-a", (1.0,)),))
        store.deactivate(("public-id",))

    assert captured[0][1]["points"][0]["id"] == _qdrant_point_id("public-id")
    assert captured[0][1]["points"][0]["payload"]["example_id"] == "public-id"
    assert captured[1][1] == {
        "payload": {"active": False},
        "points": [_qdrant_point_id("public-id")],
    }
