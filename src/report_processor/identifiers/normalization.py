"""Normalization of identifier-bearing input values."""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE_RE = re.compile(r"\s+")
_EXPLICIT_SPACES = str.maketrans({"\u00a0": " ", "\u202f": " "})


def is_supported_identifier_input(value: object) -> bool:
    """Return whether *value* can be normalized without guessing its semantics."""

    return value is None or (
        not isinstance(value, bool) and isinstance(value, (str, int, float))
    )


def normalize_identifier_text(value: object) -> str | None:
    """Normalize text while preserving digits, leading zeros and punctuation.

    Floats are represented with ``repr`` so ``1006.0`` remains ``1006.0`` and
    cannot silently become a plain integer-like identifier.
    """

    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None

    text = repr(value) if isinstance(value, float) else str(value)

    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_EXPLICIT_SPACES)
    text = text.replace("\t", " ").replace("\r", " ").replace("\n", " ")
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text or None
