"""Versioned, audit-preserving normalization for work terms."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .ontology import DomainOntology

TERM_CANONICALIZATION_VERSION = "TermCanonicalization-2.0"
_SPACE = re.compile(r"\s+")
_DASHES = re.compile(r"[‐‑‒–—―−]")
_QUOTES = str.maketrans(
    {"«": '"', "»": '"', "“": '"', "”": '"', "„": '"', "‟": '"', "’": "'", "`": "'"}
)
_TECHNICAL = {"дн": "dn", "dn": "dn", "рn": "pn", "рп": "pn", "pn": "pn"}
_DN_PREFIX = re.compile(r"(?<!\w)(?:дн|дn|dн|dn)(?=\s*\d)", re.IGNORECASE)
_PN_PREFIX = re.compile(r"(?<!\w)(?:рп|рn|pп|pn)(?=\s*\d)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class CanonicalTerm:
    """Audit and semantic identities are deliberately separate."""

    audit_text: str
    semantic_text: str
    tokens: tuple[str, ...]
    version: str = TERM_CANONICALIZATION_VERSION


def normalize_audit_text(value: Any) -> str:
    """Preserve spelling while making the stored audit value Unicode/space stable."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    return _SPACE.sub(" ", text.replace("\r", " ").replace("\n", " ")).strip()


def normalize_semantic_text(value: Any) -> str:
    """Normalize only deterministic typography; ontology owns semantic aliases."""
    text = normalize_audit_text(value).casefold().replace("ё", "е")
    text = _DASHES.sub("-", text).translate(_QUOTES)
    text = re.sub(r"(?<=\d)[хx×](?=\d)", "x", text)
    # Technical prefixes are often entered as compact mixed Cyrillic/Latin text.
    # Repair only an unambiguous DN/PN prefix immediately before a dimension.
    text = _DN_PREFIX.sub("dn", text)
    text = _PN_PREFIX.sub("pn", text)
    tokens = [
        _TECHNICAL.get(token, token)
        for token in re.findall(r"[\w.]+|[-/×]", text, flags=re.UNICODE)
    ]
    return " ".join(tokens)


def canonicalize_term(
    value: Any,
    *,
    category: str | None = None,
    object_kind: str | None = None,
    ontology: DomainOntology | None = None,
) -> CanonicalTerm:
    """Return the immutable term contract without mutating its audit identity."""
    semantic = normalize_semantic_text(value)
    if ontology is not None:
        semantic = ontology.canonicalize_text(semantic, category=category, object_kind=object_kind)
    return CanonicalTerm(
        audit_text=normalize_audit_text(value),
        semantic_text=semantic,
        tokens=tuple(token for token in semantic.split() if token not in {"-", "/"}),
    )
