"""Controlled grouping keys for inline drawing-card review."""

from __future__ import annotations

import re

from ..sources.normalization import normalize_text

_CABLE_COUPLING_PREFIX_RE = re.compile(r"^установка муфт соединительных\b", re.IGNORECASE)
_TERMINAL_NUMBER_RE = re.compile(r"\s*\(\s*№\s*\d+\s*\)\s*$", re.IGNORECASE)


def review_group_name(work_name: str | None) -> str:
    """Return a conservative grouping key without dropping semantic suffixes.

    Cable-coupling names may vary only by a terminal ``(№N)`` marker.  That
    marker is safely ignored; mass, brand, model, article, section and voltage
    remain part of the key.  All other work names use their exact normalized
    value and therefore cannot be broadly grouped by a generic word.
    """
    name = normalize_text(work_name)
    if _CABLE_COUPLING_PREFIX_RE.match(name):
        return _TERMINAL_NUMBER_RE.sub("", name).strip()
    return name
