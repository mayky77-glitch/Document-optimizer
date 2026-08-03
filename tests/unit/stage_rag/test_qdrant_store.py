"""Focused coverage for Qdrant REST tenant isolation and fallback storage."""

from __future__ import annotations

import json
from dataclasses import replace
from unittest.mock import patch
from urllib.error import URLError

import pytest

from report_processor.stage_rag.errors import StageRAGStoreUnavailableError
from report_processor.stage_rag.models import ConfirmedExampleVector, DenseRetrievalQuery
from report_processor.stage_rag.qdrant_store import InMemoryVectorStore, QdrantVectorStore


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


def test_in_memory_store_filters_tenant_and_orders_score_then_public_example_id() -> None:
    store = InMemoryVectorStore()
    store.upsert(
        (
            _example("b", "tenant-a", (1.0, 0.0)),
            _example("a", "tenant-a", (1.0, 0.0)),
            _example("foreign", "tenant-b", (1.0, 0.0)),
        )
    )

    result = store.query(DenseRetrievalQuery("tenant-a", (1.0, 0.0), limit=5))

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
                            },
                        },
                        {
                            "id": "a",
                            "score": 0.8,
                            "payload": {
                                "example_id": "a",
                                "tenant_id": "tenant-a",
                                "category": "A",
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
        result = store.query(
            DenseRetrievalQuery("tenant-a", (1.0, 0.0), project_id="p", document_type="spec")
        )

    assert captured["url"] == "http://qdrant.test/collections/confirmed_examples_v1/points/query"
    assert captured["timeout"] == 1.5
    assert captured["body"]["filter"]["must"] == [
        {"key": "tenant_id", "match": {"value": "tenant-a"}},
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
        store.query(DenseRetrievalQuery("tenant-a", (1.0,)))


def test_audit_reference_cannot_be_a_local_path() -> None:
    with pytest.raises(ValueError, match="audit_reference"):
        replace(_example("one", "tenant-a", (1.0,)), audit_reference="/private/book.xlsx")
