from __future__ import annotations

from starlette.testclient import TestClient

from report_processor.stage_rag.encoder import EMBEDDING_DIMENSIONS, RUBERT_TINY2_MODEL_ID
from report_processor.stage_rag.errors import StageRAGModelUnavailableError
from report_processor.stage_rag.service import MAX_BATCH_SIZE, MAX_TEXT_CHARACTERS, create_app


class FakeEncoder:
    def encode(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple((float(index),) * EMBEDDING_DIMENSIONS for index, _ in enumerate(texts))


class UnavailableEncoder:
    def encode(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        raise StageRAGModelUnavailableError("not available")


class InvalidVectorEncoder:
    def __init__(self, vector: tuple[float, ...]) -> None:
        self.vector = vector

    def encode(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple(self.vector for _ in texts)


def test_embeddings_returns_openai_compatible_response() -> None:
    response = TestClient(create_app(FakeEncoder())).post(
        "/v1/embeddings", json={"input": ["one", "two"], "model": RUBERT_TINY2_MODEL_ID}
    )

    assert response.status_code == 200
    assert response.json() == {
        "object": "list",
        "data": [
            {"object": "embedding", "embedding": [0.0] * EMBEDDING_DIMENSIONS, "index": 0},
            {"object": "embedding", "embedding": [1.0] * EMBEDDING_DIMENSIONS, "index": 1},
        ],
        "model": RUBERT_TINY2_MODEL_ID,
        "usage": {"prompt_tokens": 0, "total_tokens": 0},
    }


def test_embeddings_rejects_oversized_and_invalid_inputs() -> None:
    client = TestClient(create_app(FakeEncoder()))

    responses = [
        client.post("/v1/embeddings", json={"input": []}),
        client.post("/v1/embeddings", json={"input": ["x"] * (MAX_BATCH_SIZE + 1)}),
        client.post("/v1/embeddings", json={"input": ["x" * (MAX_TEXT_CHARACTERS + 1)]}),
        client.post("/v1/embeddings", json={"input": ["   "]}),
    ]

    assert all(response.status_code == 400 for response in responses)
    assert all(response.json()["error"]["code"] == "invalid_input" for response in responses)


def test_embeddings_rejects_any_non_pinned_requested_model() -> None:
    client = TestClient(create_app(FakeEncoder()))

    responses = [
        client.post("/v1/embeddings", json={"input": "text", "model": "another-model"}),
        client.post("/v1/embeddings", json={"input": "text", "model_id": "another-model"}),
        client.post("/v1/embeddings", json={"input": "text"}),
        client.post("/v1/embeddings", json={"input": "text", "model_id": RUBERT_TINY2_MODEL_ID}),
    ]

    assert all(response.status_code == 400 for response in responses)
    assert all(response.json()["error"]["code"] == "invalid_model" for response in responses)


def test_embeddings_rejects_non_finite_or_wrong_size_vectors() -> None:
    clients = [
        TestClient(create_app(InvalidVectorEncoder((0.0,) * (EMBEDDING_DIMENSIONS - 1)))),
        TestClient(create_app(InvalidVectorEncoder((float("nan"),) * EMBEDDING_DIMENSIONS))),
    ]

    responses = [
        client.post("/v1/embeddings", json={"input": "text", "model": RUBERT_TINY2_MODEL_ID})
        for client in clients
    ]

    assert all(response.status_code == 503 for response in responses)
    assert all(response.json()["error"]["code"] == "service_unavailable" for response in responses)


def test_embeddings_hides_local_model_errors() -> None:
    response = TestClient(create_app(UnavailableEncoder())).post(
        "/v1/embeddings", json={"input": "text", "model": RUBERT_TINY2_MODEL_ID}
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "model_unavailable"
    assert "text" not in response.text


def test_healthz_does_not_load_the_model() -> None:
    response = TestClient(create_app(UnavailableEncoder())).get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
