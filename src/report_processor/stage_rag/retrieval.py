"""Deterministic cosine retrieval for manual stage-relation review."""

from __future__ import annotations

from collections.abc import Sequence
from math import isfinite, sqrt

from .encoder import EMBEDDING_DIMENSIONS, StageEncoder
from .errors import StageRAGError, StageRAGInputError
from .models import StageRelationCandidate, StageRelationSuggestion, StageText


class StageRelationRAG:
    """Suggest semantic source-stage neighbours without affecting Block 12 matches."""

    def __init__(
        self, encoder: StageEncoder, *, embedding_dimensions: int = EMBEDDING_DIMENSIONS
    ) -> None:
        if not hasattr(encoder, "encode"):
            raise StageRAGInputError("INVALID_ENCODER", "encoder должен иметь метод encode")
        if isinstance(embedding_dimensions, bool) or not isinstance(embedding_dimensions, int):
            raise StageRAGInputError("INVALID_DIMENSION", "embedding_dimensions должен быть целым")
        if embedding_dimensions < 1:
            raise StageRAGInputError(
                "INVALID_DIMENSION", "embedding_dimensions должен быть положительным"
            )
        self._encoder = encoder
        self._embedding_dimensions = embedding_dimensions

    def suggest(
        self,
        source_stages: Sequence[StageText],
        target_stages: Sequence[StageText],
        *,
        k: int = 3,
    ) -> tuple[StageRelationSuggestion, ...]:
        """Return score-descending, identity-stable suggestions for manual review only."""
        sources = _validate_stages(source_stages, "source_stages")
        targets = _validate_stages(target_stages, "target_stages")
        _validate_k(k, len(sources))
        if not targets:
            return ()
        if not sources:
            return tuple(StageRelationSuggestion(item.identity, ()) for item in targets)

        source_vectors = self._encode(sources)
        target_vectors = self._encode(targets)
        suggestions = []
        for target, target_vector in zip(targets, target_vectors, strict=True):
            ranked = sorted(
                (
                    StageRelationCandidate(source.identity, _cosine(target_vector, source_vector))
                    for source, source_vector in zip(sources, source_vectors, strict=True)
                ),
                key=lambda item: (-item.score, item.source_identity),
            )
            suggestions.append(StageRelationSuggestion(target.identity, tuple(ranked[:k])))
        return tuple(suggestions)

    def _encode(self, stages: tuple[StageText, ...]) -> tuple[tuple[float, ...], ...]:
        try:
            encoded = tuple(self._encoder.encode(tuple(item.text for item in stages)))
        except StageRAGError:
            raise
        except Exception as exc:
            raise StageRAGInputError(
                "ENCODER_FAILURE", "encoder не смог вернуть embeddings"
            ) from exc
        if len(encoded) != len(stages):
            raise StageRAGInputError(
                "INVALID_VECTOR_COUNT", "encoder вернул неверное число embeddings"
            )
        return tuple(_normalise(vector, self._embedding_dimensions) for vector in encoded)


def retrieve_stage_relations(
    encoder: StageEncoder,
    source_stages: Sequence[StageText],
    target_stages: Sequence[StageText],
    *,
    k: int = 3,
    embedding_dimensions: int = EMBEDDING_DIMENSIONS,
) -> tuple[StageRelationSuggestion, ...]:
    """Convenience entry point equivalent to ``StageRelationRAG(...).suggest(...)``."""
    return StageRelationRAG(encoder, embedding_dimensions=embedding_dimensions).suggest(
        source_stages, target_stages, k=k
    )


def _validate_stages(values: Sequence[StageText], name: str) -> tuple[StageText, ...]:
    if isinstance(values, (str, bytes)):
        raise StageRAGInputError(
            "INVALID_STAGES", f"{name} должен быть последовательностью StageText"
        )
    try:
        stages = tuple(values)
    except TypeError as exc:
        raise StageRAGInputError(
            "INVALID_STAGES", f"{name} должен быть последовательностью StageText"
        ) from exc
    if any(not isinstance(item, StageText) for item in stages):
        raise StageRAGInputError("INVALID_STAGE", f"{name} должен содержать только StageText")
    identities = tuple(item.identity for item in stages)
    if len(identities) != len(set(identities)):
        raise StageRAGInputError("DUPLICATE_IDENTITY", f"{name} содержит повторяющийся identity")
    return tuple(sorted(stages, key=lambda item: item.identity))


def _validate_k(k: int, source_count: int) -> None:
    if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= max(1, source_count):
        raise StageRAGInputError("INVALID_K", "k должен быть целым от 1 до числа source_stages")


def _normalise(vector: Sequence[float], dimensions: int) -> tuple[float, ...]:
    if isinstance(vector, (str, bytes)):
        raise StageRAGInputError(
            "INVALID_VECTOR", "embedding должен быть числовой последовательностью"
        )
    try:
        values = tuple(float(value) for value in vector)
    except (TypeError, ValueError) as exc:
        raise StageRAGInputError(
            "INVALID_VECTOR", "embedding должен быть числовой последовательностью"
        ) from exc
    if len(values) != dimensions:
        raise StageRAGInputError("INVALID_VECTOR_DIMENSION", "embedding имеет неверную размерность")
    if not all(isfinite(value) for value in values):
        raise StageRAGInputError("NONFINITE_VECTOR", "embedding должен содержать конечные числа")
    length = sqrt(sum(value * value for value in values))
    if length == 0:
        raise StageRAGInputError("ZERO_VECTOR", "нулевой embedding нельзя нормализовать")
    return tuple(value / length for value in values)


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(
        left_value * right_value for left_value, right_value in zip(left, right, strict=True)
    )
