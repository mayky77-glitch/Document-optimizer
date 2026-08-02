"""Optional local semantic ranking with strict cache/version and fail-soft boundaries."""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from typing import Protocol

from .models import FeatureVector


class StageEncoder(Protocol):
    """Minimal local encoder shape; production code injects any compatible adapter."""

    def encode(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...


@dataclass(frozen=True, slots=True)
class SemanticAssistResult:
    """Non-authoritative diagnostics; callers must never derive package membership from it."""

    similarities: tuple[tuple[str, str, float], ...] = ()
    unavailable_reason: str | None = None


class VersionedEmbeddingCache:
    """In-memory cache that cannot cross model, rule or feature-contract boundaries."""

    def __init__(self) -> None:
        self._values: dict[tuple[str, str, str, str, str], tuple[float, ...]] = {}

    def get(
        self,
        feature: FeatureVector,
        *,
        model_revision: str,
    ) -> tuple[float, ...] | None:
        return self._values.get(_cache_key(feature, model_revision=model_revision))

    def put(self, feature: FeatureVector, *, model_revision: str, vector: Sequence[float]) -> None:
        self._values[_cache_key(feature, model_revision=model_revision)] = tuple(
            float(value) for value in vector
        )


class LocalSemanticAssist:
    """Bounded local encoder adapter with deterministic fail-soft fallback."""

    def __init__(
        self,
        encoder: StageEncoder,
        *,
        model_revision: str,
        timeout_seconds: float = 0.25,
        batch_size: int = 64,
        cache: VersionedEmbeddingCache | None = None,
    ) -> None:
        if not model_revision or timeout_seconds <= 0 or batch_size <= 0:
            raise ValueError("model revision, positive timeout and batch size are required")
        self._encoder = encoder
        self._model_revision = model_revision
        self._timeout_seconds = timeout_seconds
        self._batch_size = batch_size
        self._cache = cache or VersionedEmbeddingCache()

    def rank(self, features: Sequence[FeatureVector]) -> SemanticAssistResult:
        """Return optional cosine diagnostics only; hard rules and packages never consult them."""
        ordered = tuple(sorted(features, key=lambda feature: feature.group_id))
        pending: list[FeatureVector] = []
        pending_keys: set[tuple[str, str, str, str, str]] = set()
        for feature in ordered:
            key = _cache_key(feature, model_revision=self._model_revision)
            if (
                self._cache.get(feature, model_revision=self._model_revision) is None
                and key not in pending_keys
            ):
                pending.append(feature)
                pending_keys.add(key)
        if pending:
            for start in range(0, len(pending), self._batch_size):
                batch = pending[start : start + self._batch_size]
                encoded = self._encode_fail_soft(
                    tuple(feature.normalized_name for feature in batch)
                )
                if isinstance(encoded, str):
                    return SemanticAssistResult(unavailable_reason=encoded)
                for feature, vector in zip(batch, encoded, strict=True):
                    self._cache.put(feature, model_revision=self._model_revision, vector=vector)
        vectors = [
            self._cache.get(feature, model_revision=self._model_revision) for feature in ordered
        ]
        if any(vector is None for vector in vectors):
            return SemanticAssistResult(unavailable_reason="local_model_incomplete")
        similarities = tuple(
            (left.group_id, right.group_id, _cosine(left_vector, right_vector))
            for index, (left, left_vector) in enumerate(zip(ordered, vectors, strict=True))
            for right, right_vector in zip(ordered[index + 1 :], vectors[index + 1 :], strict=True)
            if left_vector is not None and right_vector is not None
        )
        return SemanticAssistResult(similarities=similarities)

    def _encode_fail_soft(self, texts: tuple[str, ...]) -> Sequence[Sequence[float]] | str:
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(self._encoder.encode, texts)
            result = future.result(timeout=self._timeout_seconds)
            if len(result) != len(texts) or any(not vector for vector in result):
                return "local_model_invalid_output"
            return result
        except TimeoutError:
            return "local_model_timeout"
        except Exception:
            return "local_model_unavailable"
        finally:
            executor.shutdown(wait=False, cancel_futures=True)


def _cache_key(feature: FeatureVector, *, model_revision: str) -> tuple[str, str, str, str, str]:
    return (
        feature.normalized_name,
        feature.unit_family.value,
        model_revision,
        feature.feature_contract_version,
        feature.rule_version,
    )


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        return 0.0
    numerator = sum(first * second for first, second in zip(left, right, strict=True))
    left_length = sum(value * value for value in left) ** 0.5
    right_length = sum(value * value for value in right) ** 0.5
    return numerator / (left_length * right_length) if left_length and right_length else 0.0
