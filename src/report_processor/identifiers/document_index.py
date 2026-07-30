"""Extraction, validation and comparison of construction document indexes."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path

from report_processor.domain.statuses import IndexStatus, IndexWarning
from report_processor.identifiers.models import (
    DocumentIndex,
    IndexCandidate,
    IndexExtractionResult,
)
from report_processor.identifiers.normalization import (
    is_supported_identifier_input,
    normalize_identifier_text,
)

MAIN_MIN_DIGITS = 3
MAIN_MAX_DIGITS = 8
SECONDARY_MIN_DIGITS = 1
SECONDARY_MAX_DIGITS = 8

PATTERN_CONFIDENCE = {
    "strict_parentheses": 1.0,
    "spaced_parentheses": 0.98,
    "loose_separator": 0.70,
}
YEAR_LIKE_CONFIDENCE = 0.60

_STRICT_RE = re.compile(
    rf"(?<!\d)(?P<main>\d{{{MAIN_MIN_DIGITS},{MAIN_MAX_DIGITS}}})"
    rf"(?P<before>\s*)\((?P<inside_before>\s*)"
    rf"(?P<secondary>\d{{{SECONDARY_MIN_DIGITS},{SECONDARY_MAX_DIGITS}}})"
    rf"(?P<inside_after>\s*)\)(?!\d)"
)
_LOOSE_RE = re.compile(
    rf"(?<![\d.])(?P<main>\d{{{MAIN_MIN_DIGITS},{MAIN_MAX_DIGITS}}})"
    rf"\s*(?P<separator>[-_/])\s*"
    rf"(?P<secondary>\d{{{SECONDARY_MIN_DIGITS},{SECONDARY_MAX_DIGITS}}})(?![\d.])"
)
_YEAR_RE = re.compile(r"(?:19|20)\d{2}\Z")
_DATE_RE = re.compile(
    r"(?<!\d)(?:\d{1,2}[-_/]\d{1,2}[-_/]\d{4}|\d{4}[-_/]\d{1,2}(?:[-_/]\d{1,2})?)(?!\d)"
)
_REJECTING_PREFIX_RE = re.compile(
    r"(?:кс|ks)\s*[-–—]?\s*|(?:ред(?:акция)?|rev(?:ision)?|этап|stage)\s*",
    re.IGNORECASE,
)


def _candidate_from_match(match: re.Match[str], pattern_type: str) -> IndexCandidate:
    main = match.group("main")
    secondary = match.group("secondary")
    fragment = match.group(0)
    document_index = DocumentIndex(
        raw=fragment,
        normalized=f"{main} ({secondary})",
        main=main,
        secondary=secondary,
    )
    return IndexCandidate(
        document_index=document_index,
        start=match.start(),
        end=match.end(),
        source_fragment=fragment,
        pattern_type=pattern_type,
        confidence=PATTERN_CONFIDENCE[pattern_type],
    )


def _has_rejecting_prefix(text: str, start: int) -> bool:
    prefix = text[max(0, start - 24) : start]
    prefix_match = _REJECTING_PREFIX_RE.search(prefix)
    return prefix_match is not None and prefix_match.end() == len(prefix)


def _strict_candidates(text: str) -> list[IndexCandidate]:
    candidates: list[IndexCandidate] = []
    for match in _STRICT_RE.finditer(text):
        if _has_rejecting_prefix(text, match.start()):
            continue
        spaced = bool(
            match.group("inside_before")
            or match.group("inside_after")
            or len(match.group("before")) > 1
        )
        pattern_type = "spaced_parentheses" if spaced else "strict_parentheses"
        candidates.append(_candidate_from_match(match, pattern_type))
    return candidates


def _has_rejecting_loose_context(text: str, candidate: IndexCandidate) -> bool:
    fragment = candidate.source_fragment
    index = candidate.document_index
    if _DATE_RE.search(fragment):
        return True
    if _YEAR_RE.fullmatch(index.main) and len(index.secondary) <= 2:
        return True

    return _has_rejecting_prefix(text, candidate.start)


def _loose_candidates(text: str) -> list[IndexCandidate]:
    candidates: list[IndexCandidate] = []
    for match in _LOOSE_RE.finditer(text):
        candidate = _candidate_from_match(match, "loose_separator")
        if not _has_rejecting_loose_context(text, candidate):
            candidates.append(candidate)
    return candidates


def _deduplicate_candidates(
    candidates: Iterable[IndexCandidate],
) -> tuple[tuple[IndexCandidate, ...], bool]:
    unique: dict[str, IndexCandidate] = {}
    duplicate_found = False
    for candidate in candidates:
        key = candidate.document_index.normalized
        if key in unique:
            duplicate_found = True
            existing = unique[key]
            if candidate.confidence > existing.confidence:
                unique[key] = candidate
        else:
            unique[key] = candidate
    return tuple(unique.values()), duplicate_found


def _apply_year_warning(
    candidates: tuple[IndexCandidate, ...],
) -> tuple[tuple[IndexCandidate, ...], bool]:
    adjusted: list[IndexCandidate] = []
    year_like = False
    for candidate in candidates:
        if _YEAR_RE.fullmatch(candidate.document_index.main):
            confidence = min(candidate.confidence, YEAR_LIKE_CONFIDENCE)
            adjusted.append(replace(candidate, confidence=confidence))
            year_like = True
        else:
            adjusted.append(candidate)
    return tuple(adjusted), year_like


def extract_document_index(
    value: object,
    *,
    allow_loose: bool = False,
) -> IndexExtractionResult:
    """Extract one unambiguous document index from a scalar value."""

    if not is_supported_identifier_input(value):
        return IndexExtractionResult(
            value=None,
            candidates=(),
            status=IndexStatus.INVALID_INPUT_TYPE.value,
            warnings=(),
            source_text=None,
        )

    text = normalize_identifier_text(value)
    if text is None:
        return IndexExtractionResult(
            value=None,
            candidates=(),
            status=IndexStatus.EMPTY_INPUT.value,
            warnings=(),
            source_text=text,
        )

    strict = _strict_candidates(text)
    raw_candidates = strict if strict or not allow_loose else _loose_candidates(text)
    candidates, duplicates = _deduplicate_candidates(raw_candidates)
    candidates, year_like = _apply_year_warning(candidates)

    warnings: list[str] = []
    if duplicates:
        warnings.append(IndexWarning.DUPLICATE_INDEX_OCCURRENCES.value)
    if year_like:
        warnings.append(IndexWarning.YEAR_LIKE_MAIN_INDEX.value)

    if not candidates:
        return IndexExtractionResult(
            value=None,
            candidates=(),
            status=IndexStatus.INDEX_NOT_FOUND.value,
            warnings=tuple(warnings),
            source_text=text,
        )
    if len(candidates) > 1:
        return IndexExtractionResult(
            value=None,
            candidates=candidates,
            status=IndexStatus.MULTIPLE_INDEX_CANDIDATES.value,
            warnings=tuple(warnings),
            source_text=text,
        )

    candidate = candidates[0]
    low_confidence = candidate.pattern_type == "loose_separator" or year_like
    return IndexExtractionResult(
        value=None if low_confidence else candidate.document_index,
        candidates=candidates,
        status=(
            IndexStatus.LOW_CONFIDENCE_INDEX.value
            if low_confidence
            else IndexStatus.OK.value
        ),
        warnings=tuple(warnings),
        source_text=text,
    )


def _portable_parts(value: str | Path) -> tuple[str, ...]:
    normalized = str(value).replace("\\", "/")
    return tuple(part for part in normalized.split("/") if part not in {"", "."})


def extract_index_from_filename(
    filename: str,
    *,
    allow_loose: bool = False,
) -> IndexExtractionResult:
    """Extract an index from a filename after removing its final extension."""

    if not isinstance(filename, str):
        return extract_document_index(filename, allow_loose=allow_loose)
    parts = _portable_parts(filename)
    leaf = parts[-1] if parts else filename
    return extract_document_index(Path(leaf).stem, allow_loose=allow_loose)


def _result_from_path_candidates(
    path_text: str,
    candidates: list[IndexCandidate],
    warnings: list[str],
) -> IndexExtractionResult:
    unique, duplicates = _deduplicate_candidates(candidates)
    unique, year_like = _apply_year_warning(unique)
    if duplicates and IndexWarning.DUPLICATE_INDEX_OCCURRENCES.value not in warnings:
        warnings.append(IndexWarning.DUPLICATE_INDEX_OCCURRENCES.value)
    if year_like and IndexWarning.YEAR_LIKE_MAIN_INDEX.value not in warnings:
        warnings.append(IndexWarning.YEAR_LIKE_MAIN_INDEX.value)

    if not unique:
        return IndexExtractionResult(
            value=None,
            candidates=(),
            status=IndexStatus.INDEX_NOT_FOUND.value,
            warnings=tuple(warnings),
            source_text=path_text,
        )
    if len(unique) > 1:
        return IndexExtractionResult(
            value=None,
            candidates=unique,
            status=IndexStatus.MULTIPLE_INDEX_CANDIDATES.value,
            warnings=tuple(warnings),
            source_text=path_text,
        )

    candidate = unique[0]
    low = candidate.pattern_type == "loose_separator" or year_like
    return IndexExtractionResult(
        value=None if low else candidate.document_index,
        candidates=unique,
        status=IndexStatus.LOW_CONFIDENCE_INDEX.value if low else IndexStatus.OK.value,
        warnings=tuple(warnings),
        source_text=path_text,
    )


def extract_index_from_path(
    path: str | Path,
    *,
    include_parent_parts: bool = False,
    allow_loose: bool = False,
) -> IndexExtractionResult:
    """Extract an index from a portable POSIX or Windows path."""

    if not isinstance(path, (str, Path)):
        return extract_document_index(path, allow_loose=allow_loose)

    path_text = str(path)
    parts = _portable_parts(path_text)
    if not parts:
        return extract_document_index("", allow_loose=allow_loose)

    filename_result = extract_index_from_filename(parts[-1], allow_loose=allow_loose)
    if not include_parent_parts:
        return filename_result

    all_candidates = list(filename_result.candidates)
    warnings = list(filename_result.warnings)
    filename_values = {c.document_index.normalized for c in filename_result.candidates}
    parent_values: set[str] = set()

    for parent in reversed(parts[:-1]):
        if re.fullmatch(r"[A-Za-z]:", parent):
            continue
        result = extract_document_index(parent, allow_loose=allow_loose)
        all_candidates.extend(result.candidates)
        parent_values.update(c.document_index.normalized for c in result.candidates)
        for warning in result.warnings:
            if warning not in warnings:
                warnings.append(warning)

    if filename_values and filename_values & parent_values:
        warnings.append(IndexWarning.INDEX_CONFIRMED_BY_PARENT_PATH.value)

    return _result_from_path_candidates(path_text, all_candidates, warnings)


def _coerce_unambiguous_index(value: DocumentIndex | str | None) -> DocumentIndex | None:
    if isinstance(value, DocumentIndex):
        return value
    if value is None:
        return None
    result = extract_document_index(value)
    return result.value if result.status == IndexStatus.OK.value else None


def document_indexes_equal(
    left: DocumentIndex | str | None,
    right: DocumentIndex | str | None,
) -> bool:
    """Compare two indexes by exact canonical string without losing zeros."""

    left_index = _coerce_unambiguous_index(left)
    right_index = _coerce_unambiguous_index(right)
    return (
        left_index is not None
        and right_index is not None
        and left_index.normalized == right_index.normalized
    )


def document_index_matches_parts(
    index: DocumentIndex,
    *,
    main: str | None = None,
    secondary: str | None = None,
) -> bool:
    """Return whether explicitly supplied index parts match exactly."""

    return (main is None or index.main == main) and (
        secondary is None or index.secondary == secondary
    )
