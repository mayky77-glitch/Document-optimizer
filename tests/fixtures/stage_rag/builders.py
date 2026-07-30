"""Small deterministic encoders and stage values for RAG tests."""

from __future__ import annotations

from collections.abc import Sequence


class FakeEncoder:
    """Map input text to explicit vectors and record calls."""

    def __init__(self, vectors: dict[str, Sequence[float]]) -> None:
        self.vectors = vectors
        self.calls: list[tuple[str, ...]] = []

    def encode(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        self.calls.append(tuple(texts))
        return tuple(tuple(self.vectors[text]) for text in texts)
