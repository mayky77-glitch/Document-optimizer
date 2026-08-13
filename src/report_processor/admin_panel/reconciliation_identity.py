"""Fail-closed terminal document identities for reconciliation only."""

from __future__ import annotations

import re
from pathlib import Path

_YEAR_RE = re.compile(r"(?:19|20)\d{2}\Z")
_BARE_RE = re.compile(r"\d{4}\Z")
_FULL_RE = re.compile(r"[\w-]+(?:\.[\w-]+)*\.(\d{3,4})\Z", re.UNICODE)
_PARENTHETICAL_RE = re.compile(r"\(([^()]*)\)")
_PRIMARY_RE = re.compile(r"(?:^|[-_])(\d{4})(?=$|[-_\s(])")


def terminal_identity(value: object) -> str | None:
    """Return one scalar terminal identity, never a prose extraction.

    A target cell is intentionally stricter than a filename: it must contain a
    bare non-year four digit identifier, or a complete dotted identifier whose
    final component is three or four digits.
    """

    text = str(value or "").strip()
    if _BARE_RE.fullmatch(text) and not _YEAR_RE.fullmatch(text):
        return text
    match = _FULL_RE.fullmatch(text)
    if match is not None:
        final = match.group(1)
        if _YEAR_RE.fullmatch(final) is None:
            return final
    return None


def source_basename_identities(safe_basename: str) -> tuple[str, ...]:
    """Return bounded primary/parenthetical candidates from one safe basename."""

    if not safe_basename or safe_basename != Path(safe_basename).name:
        raise ValueError("safe_basename must be a basename")
    stem = Path(safe_basename).stem
    values: list[str] = []
    primary = terminal_identity(stem)
    if primary is not None:
        values.append(primary)
    else:
        values.extend(
            value for value in _PRIMARY_RE.findall(stem) if _YEAR_RE.fullmatch(value) is None
        )
    for contents in _PARENTHETICAL_RE.findall(stem):
        for part in contents.split(","):
            candidate = terminal_identity(part.strip())
            if candidate is not None:
                values.append(candidate)
    return tuple(dict.fromkeys(values))


def resolve_source_identity(
    candidates: tuple[str, ...], target_identities: set[str] | frozenset[str]
) -> str | None:
    """Resolve a source only through one selected-stage terminal intersection."""

    matches = tuple(candidate for candidate in candidates if candidate in target_identities)
    return matches[0] if len(matches) == 1 else None
