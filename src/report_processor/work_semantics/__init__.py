"""Isolated shared work semantics contracts; no legacy pipeline integration."""

from .canonicalization import (
    TERM_CANONICALIZATION_VERSION,
    CanonicalTerm,
    canonicalize_term,
    normalize_audit_text,
    normalize_semantic_text,
)
from .ontology import (
    DEFAULT_ONTOLOGY,
    DOMAIN_ONTOLOGY_VERSION,
    UNIT_ONTOLOGY_VERSION,
    DomainOntology,
    SemanticConflict,
    SemanticLabels,
    UnitIdentity,
    canonical_unit,
    extract_semantic_labels,
    units_compatible,
)

__all__ = [
    "DEFAULT_ONTOLOGY",
    "DOMAIN_ONTOLOGY_VERSION",
    "TERM_CANONICALIZATION_VERSION",
    "UNIT_ONTOLOGY_VERSION",
    "CanonicalTerm",
    "DomainOntology",
    "SemanticConflict",
    "SemanticLabels",
    "UnitIdentity",
    "canonical_unit",
    "canonicalize_term",
    "extract_semantic_labels",
    "normalize_audit_text",
    "normalize_semantic_text",
    "units_compatible",
]
