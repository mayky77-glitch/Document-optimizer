"""Bounded, conservative text masks for drawing-card dictionary rules."""

from __future__ import annotations

import re
from functools import lru_cache

from ..sources.normalization import normalize_text

_TOKEN_RE = re.compile(r"[0-9a-zа-я]+|м/к", re.IGNORECASE)
_DISTINCTIVE_TOKEN_LENGTH = 6


@lru_cache(maxsize=256)
def _normalized(value: str) -> str:
    """Avoid re-normalizing one source row for every dictionary mask."""
    return normalize_text(value)


@lru_cache(maxsize=256)
def _tokens(value: str) -> tuple[str, ...]:
    """Normalize one reusable mask; the bounded cache never stores source rows."""
    return tuple(_TOKEN_RE.findall(_normalized(value)))


@lru_cache(maxsize=256)
def _phrase_pattern(value: str) -> re.Pattern[str]:
    tokens = _tokens(value)
    if not tokens:
        return re.compile(r"(?!x)x")
    separator = r"(?:[^0-9a-zа-я]+)"
    return re.compile(
        r"(?<![0-9a-zа-я])" + separator.join(re.escape(token) for token in tokens),
        re.IGNORECASE,
    )


def _edit_distance_at_most_one(left: str, right: str) -> bool:
    if abs(len(left) - len(right)) > 1:
        return False
    if left == right:
        return True
    if len(left) == len(right):
        return sum(a != b for a, b in zip(left, right, strict=True)) <= 1
    longer, shorter = (left, right) if len(left) > len(right) else (right, left)
    index = offset = 0
    while index < len(shorter) and offset <= 1:
        if longer[index + offset] != shorter[index]:
            offset += 1
        else:
            index += 1
    return offset <= 1


def _token_matches(mask: str, candidate: str) -> bool:
    if candidate.startswith(mask):
        return True
    return (
        len(mask) >= _DISTINCTIVE_TOKEN_LENGTH
        and len(candidate) >= _DISTINCTIVE_TOKEN_LENGTH
        and _edit_distance_at_most_one(mask, candidate)
    )


def contains_mask(text: str, mask: str) -> bool:
    """Match a mask, allowing one-edit typos only for distinctive long tokens."""
    normalized = _normalized(text)
    phrase = _normalized(mask)
    if not phrase:
        return False
    if _phrase_pattern(phrase).search(normalized) is not None:
        return True
    mask_tokens = _tokens(phrase)
    source_tokens = _tokens(normalized)
    if len(mask_tokens) != 1:
        return False
    return any(_token_matches(mask_tokens[0], token) for token in source_tokens)


def has_any_mask(text: str, masks: tuple[str, ...]) -> bool:
    return any(contains_mask(text, mask) for mask in masks)


def has_all_masks(text: str, masks: tuple[str, ...]) -> bool:
    return all(contains_mask(text, mask) for mask in masks)
