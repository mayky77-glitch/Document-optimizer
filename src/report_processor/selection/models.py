from __future__ import annotations

from dataclasses import dataclass

from report_processor.domain.models import FileManifestEntry
from report_processor.identifiers.models import DocumentIndex
from report_processor.metadata.periods import DocumentPeriod


@dataclass(frozen=True, slots=True)
class SourceSelectionRequest:
    target_index: DocumentIndex
    target_period: DocumentPeriod | None
    preferred_document_types: tuple[str, ...]
    allowed_document_types: tuple[str, ...]
    require_exact_period: bool = False
    allow_unknown_period: bool = True
    include_probable_copies: bool = False
    include_outdated: bool = False
    include_drafts: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "preferred_document_types",
            tuple(item.strip().lower() for item in self.preferred_document_types if item.strip()),
        )
        object.__setattr__(
            self,
            "allowed_document_types",
            tuple(item.strip().lower() for item in self.allowed_document_types if item.strip()),
        )


@dataclass(frozen=True, slots=True)
class ScoreComponent:
    code: str
    points: int
    explanation: str


@dataclass(frozen=True, slots=True)
class SourceCandidate:
    file_id: str
    entry: FileManifestEntry
    score: int
    rank: int | None
    accepted: bool
    rejection_reasons: tuple[str, ...]
    score_components: tuple[ScoreComponent, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CandidateFilterResult:
    accepted: tuple[SourceCandidate, ...]
    rejected: tuple[SourceCandidate, ...]
    inspected_count: int


@dataclass(frozen=True, slots=True)
class SourceSelectionResult:
    selected: SourceCandidate | None
    candidates: tuple[SourceCandidate, ...]
    rejected: tuple[SourceCandidate, ...]
    status: str
    warnings: tuple[str, ...]
    explanation: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SourceScoringConfig:
    exact_index_match: int = 100
    exact_period_match: int = 40
    preferred_type_first: int = 30
    preferred_type_step: int = 5
    final_version: int = 8
    approved_version: int = 6
    numeric_revision_step: int = 1
    numeric_revision_max_bonus: int = 20
    unknown_period: int = -10
    period_mismatch: int = -40
    probable_copy: int = -20
    outdated: int = -100
    draft: int = -30
