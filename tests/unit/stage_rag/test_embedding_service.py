from __future__ import annotations

from starlette.testclient import TestClient

from report_processor.stage_rag.errors import StageRAGModelUnavailableError
from report_processor.stage_rag.service import MAX_BATCH_SIZE, MAX_TEXT_CHARACTERS, create_app


class FakeEncoder:
    def encode(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple((float(index), 1.0) for index, _ in enumerate(texts))


class UnavailableEncoder:
    def encode(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        raise StageRAGModelUnavailableError("not available")


def test_embeddings_returns_openai_compatible_response() -> None:
    response = TestClient(create_app(FakeEncoder())).post(
        "/v1/embeddings", json={"input": ["one", "two"], "model": "local-rubert"}
    )

    assert response.status_code == 200
    assert response.json() == {
        "object": "list",
        "data": [
            {"object": "embedding", "embedding": [0.0, 1.0], "index": 0},
            {"object": "embedding", "embedding": [1.0, 1.0], "index": 1},
        ],
        "model": "local-rubert",
        "usage": {"prompt_tokens": 0, "total_tokens": 0},
    }


def test_embeddings_rejects_oversized_and_invalid_inputs() -> None:
    client = TestClient(create_app(FakeEncoder()))

    responses = [
        client.post("/v1/embeddings", json={"input": []}),
        client.post("/v1/embeddings", json={"input": ["x"] * (MAX_BATCH_SIZE + 1)}),
        client.post("/v1/embeddings", json={"input": ["x" * (MAX_TEXT_CHARACTERS + 1)]}),
    ]

    assert all(response.status_code == 400 for response in responses)
    assert all(response.json()["error"]["code"] == "invalid_input" for response in responses)


def test_embeddings_hides_local_model_errors() -> None:
    response = TestClient(create_app(UnavailableEncoder())).post(
        "/v1/embeddings", json={"input": "text"}
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "model_unavailable"
    assert "text" not in response.text


def test_healthz_does_not_load_the_model() -> None:
    response = TestClient(create_app(UnavailableEncoder())).get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
