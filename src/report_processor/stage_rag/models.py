"""Immutable, manual-review-only values returned by StageRelationRAG-18.0."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from math import isfinite

STAGE_RELATION_RAG_CONTRACT_VERSION = "StageRelationRAG-18.0"


@dataclass(frozen=True, slots=True)
class StageText:
    """A stable stage identity and the text supplied to an embedding encoder."""

    identity: str
    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.identity, str) or not self.identity.strip():
            raise ValueError("identity должен быть непустой строкой")
        if not isinstance(self.text, str):
            raise TypeError("text должен быть строкой")


@dataclass(frozen=True, slots=True, order=True)
class StageRelationCandidate:
    """One semantic neighbour; it never represents an accepted Block 12 match."""

    source_identity: str
    score: float


@dataclass(frozen=True, slots=True)
class StageRelationSuggestion:
    """A deterministic semantic suggestion that always requires manual review."""

    target_identity: str
    candidates: tuple[StageRelationCandidate, ...]
    requires_manual_review: bool = field(default=True, init=False)
    auto_accepted: bool = field(default=False, init=False)
    contract_version: str = field(default=STAGE_RELATION_RAG_CONTRACT_VERSION, init=False)


@dataclass(frozen=True, slots=True)
class ConfirmedExampleVector:
    """A validated, auditable vector for one explicit review confirmation."""

    example_id: str
    tenant_id: str
    vector: tuple[float, ...]
    normalized_text_hash: str
    embedding_model_id: str
    embedding_model_revision: str
    taxonomy_version: str
    review_decision: str
    category: str | None = None
    project_id: str | None = None
    document_type: str | None = None
    rule_version: str | None = None
    audit_reference: str | None = None
    active: bool = True

    def __post_init__(self) -> None:
        _required_strings(
            self.example_id,
            self.tenant_id,
            self.normalized_text_hash,
            self.embedding_model_id,
            self.embedding_model_revision,
            self.taxonomy_version,
            self.review_decision,
        )
        values = tuple(float(value) for value in self.vector)
        if not values or not all(isfinite(value) for value in values):
            raise ValueError("vector должен содержать хотя бы одно конечное число")
        if self.audit_reference is not None and _unsafe_audit_reference(self.audit_reference):
            raise ValueError("audit_reference должен быть opaque ID, а не URI или путём")
        if self.review_decision != "confirmed":
            raise ValueError("review_decision должен быть confirmed")
        object.__setattr__(self, "vector", values)

    @property
    def embedding_dimensions(self) -> int:
        return len(self.vector)

    def payload(self) -> dict[str, str | int | bool]:
        """Return only metadata allowed in the vector-store payload."""
        values: dict[str, str | int | bool] = {
            "example_id": self.example_id,
            "tenant_id": self.tenant_id,
            "normalized_text_hash": self.normalized_text_hash,
            "embedding_model_id": self.embedding_model_id,
            "embedding_model_revision": self.embedding_model_revision,
            "embedding_dimensions": self.embedding_dimensions,
            "taxonomy_version": self.taxonomy_version,
            "review_decision": self.review_decision,
            "active": self.active,
        }
        for key in ("category", "project_id", "document_type", "rule_version", "audit_reference"):
            value = getattr(self, key)
            if value is not None:
                values[key] = value
        return values


@dataclass(frozen=True, slots=True)
class DenseRetrievalQuery:
    """A tenant-scoped vector query with optional exact metadata constraints."""

    tenant_id: str
    vector: tuple[float, ...]
    embedding_model_id: str
    embedding_model_revision: str
    embedding_dimensions: int
    limit: int = 5
    project_id: str | None = None
    document_type: str | None = None
    taxonomy_version: str | None = None

    def __post_init__(self) -> None:
        _required_strings(self.tenant_id, self.embedding_model_id, self.embedding_model_revision)
        values = tuple(float(value) for value in self.vector)
        if not values or not all(isfinite(value) for value in values):
            raise ValueError("vector должен содержать хотя бы одно конечное число")
        if isinstance(self.limit, bool) or not isinstance(self.limit, int) or self.limit < 1:
            raise ValueError("limit должен быть положительным целым")
        if (
            isinstance(self.embedding_dimensions, bool)
            or not isinstance(self.embedding_dimensions, int)
            or self.embedding_dimensions != len(values)
        ):
            raise ValueError("embedding_dimensions должен совпадать с размерностью vector")
        object.__setattr__(self, "vector", values)


DenseQuery = DenseRetrievalQuery


@dataclass(frozen=True, slots=True)
class DenseRetrievalCandidate:
    """A candidate that can only enrich a manual-review decision."""

    example_id: str
    score: float
    category: str | None = None
    review_decision: str | None = None
    taxonomy_version: str | None = None
    requires_manual_review: bool = field(default=True, init=False)
    auto_accepted: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        _required_strings(self.example_id)
        if not isfinite(float(self.score)):
            raise ValueError("score должен быть конечным числом")
        object.__setattr__(self, "score", float(self.score))


@dataclass(frozen=True, slots=True)
class DenseRetrievalResult:
    """A deterministic result, including a controlled unavailable fallback state."""

    query: DenseRetrievalQuery
    candidates: tuple[DenseRetrievalCandidate, ...]
    index_identity: str = "unavailable"
    unavailable: bool = False
    requires_manual_review: bool = field(default=True, init=False)
    auto_accepted: bool = field(default=False, init=False)
    contract_version: str = field(default="DenseRetriever-1.0", init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.query, DenseRetrievalQuery):
            raise TypeError("query должен быть DenseRetrievalQuery")
        candidates = tuple(self.candidates)
        if any(not isinstance(item, DenseRetrievalCandidate) for item in candidates):
            raise TypeError("candidates должен содержать DenseRetrievalCandidate")
        ordered = tuple(sorted(candidates, key=lambda item: (-item.score, item.example_id)))
        if candidates != ordered:
            raise ValueError("candidates должен быть отсортирован по score и example_id")
        if self.unavailable and candidates:
            raise ValueError("unavailable result не должен содержать candidates")
        if not isinstance(self.index_identity, str) or not self.index_identity.strip():
            raise ValueError("index_identity должен быть непустой строкой")
        object.__setattr__(self, "candidates", candidates)


def _required_strings(*values: str) -> None:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError("обязательные metadata поля должны быть непустыми строками")


def _unsafe_audit_reference(value: str) -> bool:
    return not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", value) is None
