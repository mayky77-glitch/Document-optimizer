"""Bounded local-only OpenAI-compatible embeddings HTTP service."""

from __future__ import annotations

from collections.abc import Sequence
from math import isfinite
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .encoder import EMBEDDING_DIMENSIONS, RUBERT_TINY2_MODEL_ID, RuBERTTiny2Encoder, StageEncoder
from .errors import StageRAGModelUnavailableError

MAX_BATCH_SIZE = 32
MAX_TEXT_CHARACTERS = 8_192
EMBEDDING_OBJECT = "embedding"


def _error(status_code: int, message: str, code: str) -> JSONResponse:
    return JSONResponse(
        {"error": {"message": message, "type": "invalid_request_error", "code": code}},
        status_code=status_code,
    )


def _parse_input(payload: Any) -> tuple[str, ...] | None:
    if not isinstance(payload, dict):
        return None
    raw_input = payload.get("input")
    if isinstance(raw_input, str):
        texts = (raw_input,)
    elif isinstance(raw_input, list):
        texts = tuple(raw_input)
    else:
        return None
    if not texts or not all(isinstance(text, str) and text.strip() for text in texts):
        return None
    if len(texts) > MAX_BATCH_SIZE or any(len(text) > MAX_TEXT_CHARACTERS for text in texts):
        return None
    return tuple(texts)


def _has_pinned_model(payload: dict[str, Any]) -> bool:
    return payload.get("model") == RUBERT_TINY2_MODEL_ID


def _normalise_vectors(vectors: Sequence[Sequence[float]]) -> tuple[tuple[float, ...], ...] | None:
    normalised: list[tuple[float, ...]] = []
    try:
        for vector in vectors:
            values = tuple(float(value) for value in vector)
            if len(values) != EMBEDDING_DIMENSIONS or not all(isfinite(value) for value in values):
                return None
            normalised.append(values)
    except (TypeError, ValueError):
        return None
    return tuple(normalised)


def create_app(encoder: StageEncoder | None = None) -> Starlette:
    """Create an app without loading the local model until the first request."""

    local_encoder = encoder or RuBERTTiny2Encoder()

    async def healthz(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    async def embeddings(request: Request) -> JSONResponse:
        try:
            payload = await request.json()
        except Exception:
            return _error(400, "Request body must be valid JSON.", "invalid_json")

        texts = _parse_input(payload)
        if texts is None:
            return _error(
                400,
                "input must contain "
                f"1..{MAX_BATCH_SIZE} strings of at most {MAX_TEXT_CHARACTERS} characters.",
                "invalid_input",
            )
        assert isinstance(payload, dict)
        if not _has_pinned_model(payload):
            return _error(
                400, "Requested model must match the pinned local model.", "invalid_model"
            )
        try:
            vectors: Sequence[Sequence[float]] = local_encoder.encode(texts)
        except StageRAGModelUnavailableError:
            return _error(503, "The local embedding model is unavailable.", "model_unavailable")
        except Exception:
            return _error(503, "The local embedding service is unavailable.", "service_unavailable")

        normalised_vectors = _normalise_vectors(vectors)
        if normalised_vectors is None or len(normalised_vectors) != len(texts):
            return _error(503, "The local embedding service is unavailable.", "service_unavailable")
        return JSONResponse(
            {
                "object": "list",
                "data": [
                    {"object": EMBEDDING_OBJECT, "embedding": list(vector), "index": index}
                    for index, vector in enumerate(normalised_vectors)
                ],
                "model": RUBERT_TINY2_MODEL_ID,
                "usage": {"prompt_tokens": 0, "total_tokens": 0},
            }
        )

    return Starlette(
        routes=[Route("/healthz", healthz), Route("/v1/embeddings", embeddings, methods=["POST"])],
    )


app = create_app()
