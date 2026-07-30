"""Immutable, manual-review-only values returned by StageRelationRAG-18.0."""

from __future__ import annotations

from dataclasses import dataclass, field

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
