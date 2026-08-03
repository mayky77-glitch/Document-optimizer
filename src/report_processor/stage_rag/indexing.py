"""Idempotent lifecycle handling for explicitly confirmed Dense RAG examples."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from re import fullmatch, sub

from .contracts import EmbeddingProvider, VectorStore
from .errors import StageRAGInputError
from .models import ConfirmedExampleVector


@dataclass(frozen=True, slots=True)
class ConfirmedReviewOutcome:
    """Sanitized data from one explicit manual-review confirmation only."""

    tenant_id: str
    text: str
    category: str
    taxonomy_version: str
    rule_version: str
    audit_reference: str
    confirmed: bool
    project_id: str | None = None
    document_type: str | None = None
    replaces_example_id: str | None = None
    cancelled_example_ids: tuple[str, ...] = ()


class ConfirmedExampleIndexer:
    """Builds version-bound points without changing Qdrant aliases or collections."""

    def __init__(self, vector_store: VectorStore, embedding_provider: EmbeddingProvider) -> None:
        self._vector_store = vector_store
        self._embedding_provider = embedding_provider

    def index(self, outcome: ConfirmedReviewOutcome) -> ConfirmedExampleVector:
        """Upsert one confirmed outcome before deactivating distinct stale evidence."""
        _validate_outcome(outcome)
        if outcome.confirmed is not True:
            raise StageRAGInputError(
                "UNCONFIRMED_OUTCOME",
                "индексировать можно только явное manual-review подтверждение",
            )
        replacement_ids = _validated_replacement_ids(outcome)
        normalized_hash = normalized_text_hash(outcome.text)
        example_id = stable_example_id(outcome.tenant_id, outcome.audit_reference)
        vector = _encode_one(self._embedding_provider, outcome.text)
        point = ConfirmedExampleVector(
            example_id=example_id,
            tenant_id=outcome.tenant_id,
            vector=vector,
            normalized_text_hash=normalized_hash,
            embedding_model_id=self._embedding_provider.model_id,
            embedding_model_revision=self._embedding_provider.revision,
            taxonomy_version=outcome.taxonomy_version,
            review_decision="confirmed",
            category=outcome.category,
            project_id=outcome.project_id,
            document_type=outcome.document_type,
            rule_version=outcome.rule_version,
            audit_reference=outcome.audit_reference,
            active=True,
        )
        deactivated = tuple(
            example_id for example_id in replacement_ids if example_id != point.example_id
        )
        self._vector_store.upsert((point,))
        if deactivated:
            self._vector_store.deactivate(outcome.tenant_id, deactivated)
        return point

    def cancel(self, tenant_id: str, example_ids: Sequence[str]) -> None:
        """Deactivate search state without modifying any audit evidence."""
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise StageRAGInputError("INVALID_TENANT", "tenant_id должен быть непустой строкой")
        if isinstance(example_ids, (str, bytes)):
            raise StageRAGInputError(
                "INVALID_EXAMPLE_IDS", "example_ids должен быть последовательностью ID"
            )
        try:
            ids = tuple(example_ids)
        except TypeError as exc:
            raise StageRAGInputError(
                "INVALID_EXAMPLE_IDS", "example_ids должен быть последовательностью ID"
            ) from exc
        if any(not isinstance(example_id, str) or not example_id.strip() for example_id in ids):
            raise StageRAGInputError("INVALID_EXAMPLE_IDS", "example_ids содержит недопустимый ID")
        self._vector_store.deactivate(tenant_id, ids)


@dataclass(frozen=True, slots=True)
class CollectionReindexPlan:
    """Declarative reindex/rollback intent; this object never performs an alias switch."""

    source_collection: str
    target_collection: str
    alias_name: str
    rollback_collection: str
    embedding_model_id: str
    embedding_model_revision: str
    taxonomy_version: str


def plan_reindex(
    source_collection: str,
    *,
    collection_version: int,
    embedding_model_id: str,
    embedding_model_revision: str,
    taxonomy_version: str,
) -> CollectionReindexPlan:
    """Prepare a versioned target and explicit rollback target, without side effects."""
    if (
        isinstance(collection_version, bool)
        or not isinstance(collection_version, int)
        or collection_version < 1
    ):
        raise StageRAGInputError(
            "INVALID_COLLECTION_VERSION", "collection_version должен быть положительным"
        )
    _required_strings(
        source_collection, embedding_model_id, embedding_model_revision, taxonomy_version
    )
    return CollectionReindexPlan(
        source_collection=source_collection,
        target_collection=f"confirmed_examples_v{collection_version}",
        alias_name="confirmed_examples_current",
        rollback_collection=source_collection,
        embedding_model_id=embedding_model_id,
        embedding_model_revision=embedding_model_revision,
        taxonomy_version=taxonomy_version,
    )


def normalized_text_hash(text: str) -> str:
    """Hash normalized text; callers must never persist the raw input in metadata."""
    if not isinstance(text, str) or not text.strip():
        raise StageRAGInputError("INVALID_TEXT", "text должен быть непустой строкой")
    normalized = sub(r"\s+", " ", text.casefold()).strip()
    return sha256(normalized.encode("utf-8")).hexdigest()


def stable_example_id(tenant_id: str, audit_reference: str) -> str:
    """Create a stable public ID scoped to tenant and immutable review evidence."""
    _required_strings(tenant_id, audit_reference)
    return sha256(f"{tenant_id}\x00{audit_reference}".encode()).hexdigest()


def _encode_one(provider: EmbeddingProvider, text: str) -> tuple[float, ...]:
    try:
        vectors = tuple(provider.encode((text,)))
    except Exception as exc:
        raise StageRAGInputError("ENCODER_FAILURE", "embedding provider недоступен") from exc
    if len(vectors) != 1:
        raise StageRAGInputError("INVALID_VECTOR_COUNT", "provider вернул неверное число vectors")
    try:
        vector = tuple(float(value) for value in vectors[0])
        dimensions = provider.dimensions
    except (TypeError, ValueError, AttributeError) as exc:
        raise StageRAGInputError("INVALID_VECTOR", "provider вернул недопустимый vector") from exc
    if not vector or not all(isfinite(value) for value in vector):
        raise StageRAGInputError("NONFINITE_VECTOR", "vector должен содержать конечные числа")
    if isinstance(dimensions, bool) or not isinstance(dimensions, int) or len(vector) != dimensions:
        raise StageRAGInputError(
            "INVALID_VECTOR_DIMENSION", "vector не совпадает с metadata dimensions"
        )
    return vector


def _validated_replacement_ids(outcome: ConfirmedReviewOutcome) -> tuple[str, ...]:
    replacement = outcome.replaces_example_id
    if replacement is not None:
        _validate_opaque_id(replacement, "replaces_example_id")
    cancelled = outcome.cancelled_example_ids
    if isinstance(cancelled, (str, bytes)) or not isinstance(cancelled, Sequence):
        raise StageRAGInputError(
            "INVALID_EXAMPLE_IDS",
            "cancelled_example_ids должен быть конечной последовательностью ID",
        )
    for example_id in cancelled:
        _validate_opaque_id(example_id, "cancelled_example_ids")
    ids = ((replacement,) if replacement is not None else ()) + tuple(cancelled)
    return tuple(sorted(set(ids)))


def _validate_opaque_id(value: object, field_name: str) -> None:
    if not isinstance(value, str) or fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", value) is None:
        raise StageRAGInputError("INVALID_EXAMPLE_IDS", f"{field_name} содержит недопустимый ID")


def _validate_outcome(outcome: ConfirmedReviewOutcome) -> None:
    if not isinstance(outcome, ConfirmedReviewOutcome):
        raise StageRAGInputError("INVALID_OUTCOME", "ожидался ConfirmedReviewOutcome")
    _required_strings(
        outcome.tenant_id,
        outcome.category,
        outcome.taxonomy_version,
        outcome.rule_version,
        outcome.audit_reference,
    )


def _required_strings(*values: str) -> None:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise StageRAGInputError("INVALID_METADATA", "metadata должна содержать непустые строки")
