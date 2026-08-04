"""Build a canonical semantic skeleton without losing typed-slot audit evidence."""

from __future__ import annotations

from dataclasses import dataclass

from .canonicalization import TERM_CANONICALIZATION_VERSION, canonicalize_term
from .ontology import DEFAULT_ONTOLOGY, DomainOntology
from .typed_slots import (
    TYPED_SLOTS_VERSION,
    SlotConflict,
    SlotKind,
    SlotWarning,
    TypedSlot,
    TypedSlotParse,
    parse_typed_slots,
)

SEMANTIC_SKELETON_VERSION = "SemanticSkeleton-1.0"


@dataclass(frozen=True, slots=True)
class SemanticSkeleton:
    audit_text: str
    semantic_text: str
    skeleton_text: str
    slots: tuple[TypedSlot, ...]
    warnings: tuple[SlotWarning, ...]
    conflicts: tuple[SlotConflict, ...]
    requires_manual_review: bool
    typed_slots_version: str = TYPED_SLOTS_VERSION
    canonicalization_version: str = TERM_CANONICALIZATION_VERSION
    version: str = SEMANTIC_SKELETON_VERSION


def build_semantic_skeleton(
    value: object,
    *,
    category: str | None = None,
    object_kind: str | None = None,
    ontology: DomainOntology = DEFAULT_ONTOLOGY,
) -> SemanticSkeleton:
    """Mask slots structurally, then compose the accepted Wave 1 contract."""
    parsed: TypedSlotParse = parse_typed_slots(value, object_kind=object_kind)
    pieces: list[str] = []
    cursor = 0
    for slot in parsed.slots:
        _append_piece(
            pieces,
            canonicalize_term(
                parsed.audit_text[cursor : slot.span.start],
                category=category,
                object_kind=object_kind,
                ontology=ontology,
            ).semantic_text,
        )
        _append_piece(
            pieces, "" if slot.kind is SlotKind.DOCUMENT_INDEX else f"<{slot.kind.value}>"
        )
        cursor = slot.span.end
    _append_piece(
        pieces,
        canonicalize_term(
            parsed.audit_text[cursor:],
            category=category,
            object_kind=object_kind,
            ontology=ontology,
        ).semantic_text,
    )
    semantic_text = canonicalize_term(
        parsed.audit_text, category=category, object_kind=object_kind, ontology=ontology
    ).semantic_text
    return SemanticSkeleton(
        parsed.audit_text,
        semantic_text,
        "".join(pieces).strip(),
        parsed.slots,
        parsed.warnings,
        parsed.conflicts,
        parsed.requires_manual_review,
    )


def _append_piece(pieces: list[str], piece: str) -> None:
    """Reassemble canonical fragments without sentinels that user text can collide with."""
    if not piece:
        return
    if not pieces or piece[0] in ",;:.)]" or pieces[-1].endswith("(["):
        pieces.append(piece)
    else:
        pieces.append(f" {piece}")
