from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from report_processor.selection.models import SourceCandidate
from report_processor.selection.scoring import (
    has_exact_period_component,
    preferred_type_points,
)

_MIN_DATETIME = datetime.min.replace(tzinfo=UTC)


def rank_source_candidates(
    candidates: tuple[SourceCandidate, ...] | list[SourceCandidate],
) -> tuple[SourceCandidate, ...]:
    ordered = sorted(candidates, key=_technical_sort_key)
    return tuple(replace(candidate, rank=position) for position, candidate in enumerate(ordered, 1))


def business_rank_key(candidate: SourceCandidate) -> tuple[object, ...]:
    revision = candidate.entry.document_revision
    return (
        candidate.score,
        preferred_type_points(candidate),
        has_exact_period_component(candidate),
        revision.number if revision and revision.number is not None else -1,
        candidate.entry.is_final,
        candidate.entry.is_approved,
    )


def top_candidates_are_ambiguous(candidates: tuple[SourceCandidate, ...]) -> bool:
    if len(candidates) < 2:
        return False
    top_key = business_rank_key(candidates[0])
    return business_rank_key(candidates[1]) == top_key


def _technical_sort_key(candidate: SourceCandidate) -> tuple[object, ...]:
    score, type_points, exact_period, revision, is_final, is_approved = business_rank_key(candidate)
    modified = _normalized_modified_at(candidate.entry.modified_at)
    return (
        -int(score),
        -int(type_points),
        -int(exact_period),
        -int(revision),
        -int(is_final),
        -int(is_approved),
        -modified.timestamp(),
        candidate.entry.relative_path.replace("\\", "/").casefold(),
        candidate.file_id,
    )


def _normalized_modified_at(value: datetime | None) -> datetime:
    if value is None:
        return _MIN_DATETIME
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
