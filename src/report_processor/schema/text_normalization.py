"""Deterministic normalization for sheet names and structural headers."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

_DASHES_RE = re.compile(r"[‐‑‒–—―−]")
_WHITESPACE_RE = re.compile(r"\s+")
_PUNCTUATION_RE = re.compile(r"[^0-9a-zа-я+%\-]+", re.IGNORECASE)
_UNIT_RE = re.compile(r"\bед\s*\.?\s*изм\s*\.?\b", re.IGNORECASE)
_UNIT_SHORT_RE = re.compile(r"\bединиц[аы]?\s+измерени[яй]\b", re.IGNORECASE)


def normalize_unicode(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("ё", "е").replace("Ё", "Е").lower()
    text = _DASHES_RE.sub("-", text)
    return _WHITESPACE_RE.sub(" ", text.replace("\r", " ").replace("\n", " ")).strip()


def normalize_header_text(value: Any) -> str:
    text = normalize_unicode(value)
    text = _UNIT_RE.sub("единица измерения", text)
    text = _UNIT_SHORT_RE.sub("единица измерения", text)
    text = text.replace("объём", "объем")
    text = text.replace("№", " номер ")
    text = re.sub(r"\bno\b", " номер ", text)
    text = text.replace("/", " ")
    text = _PUNCTUATION_RE.sub(" ", text)
    return _WHITESPACE_RE.sub(" ", text).strip(" -")


def normalize_sheet_name(value: Any) -> str:
    text = normalize_unicode(value).replace("_", " ")
    return _WHITESPACE_RE.sub(" ", text).strip()


def normalized_tokens(value: Any) -> tuple[str, ...]:
    return tuple(token for token in normalize_header_text(value).split() if token)


def compact_sheet_name(value: Any) -> str:
    return re.sub(r"[^0-9a-zа-я]+", "", normalize_sheet_name(value))


def clean_display_text(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    return _WHITESPACE_RE.sub(" ", text.replace("\r", " ").replace("\n", " ")).strip()
