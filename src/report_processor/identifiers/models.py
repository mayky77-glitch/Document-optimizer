"""Immutable models for document identifiers."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DocumentIndex:
    """A document index with its source and canonical representations."""

    raw: str
    normalized: str
    main: str
    secondary: str


@dataclass(frozen=True, slots=True)
class IndexCandidate:
    """One index occurrence detected in source text."""

    document_index: DocumentIndex
    start: int
    end: int
    source_fragment: str
    pattern_type: str
    confidence: float


@dataclass(frozen=True, slots=True)
class IndexExtractionResult:
    """Deterministic result of document-index extraction."""

    value: DocumentIndex | None
    candidates: tuple[IndexCandidate, ...]
    status: str
    warnings: tuple[str, ...]
    source_text: str | None
