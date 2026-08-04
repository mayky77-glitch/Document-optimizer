from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from report_processor.work_semantics.semantic_skeleton import (
    SEMANTIC_SKELETON_VERSION,
    SemanticSkeleton,
    build_semantic_skeleton,
)


def test_skeleton_masks_slots_in_span_order_and_keeps_audit_and_semantic_separate() -> None:
    result = build_semantic_skeleton(
        "Монтаж кабеля, марка: ВВГнг-LS 4×16 мм², 0,66 кВ", object_kind="cable"
    )

    assert result.audit_text == "Монтаж кабеля, марка: ВВГнг-LS 4×16 мм2, 0,66 кВ"
    assert result.semantic_text == "монтаж кабеля марка ввгнг - ls 4x16 мм2 0 66 кв"
    assert result.skeleton_text == "монтаж кабеля <brand> <cable_section> <voltage>"
    assert result.audit_text != result.semantic_text != result.skeleton_text
    assert [slot.kind.value for slot in result.slots] == ["brand", "cable_section", "voltage"]


def test_document_index_is_audit_slot_but_is_removed_from_family_identity() -> None:
    result = build_semantic_skeleton("Монтаж трубопровода DN50 PN16, индекс документа: 1006-01")

    assert [slot.kind.value for slot in result.slots] == ["diameter", "pressure", "document_index"]
    assert result.skeleton_text == "монтаж трубопровод <diameter> <pressure>"
    assert "1006-01" not in result.skeleton_text
    assert "document_index" not in result.skeleton_text


def test_invalid_and_ambiguous_fragments_remain_literal_in_the_skeleton() -> None:
    result = build_semantic_skeleton("Монтаж D57 и 10-6 кВ")

    assert {item.code for item in result.warnings} >= {"ambiguous_diameter", "invalid_range"}
    assert result.requires_manual_review
    assert "d57" in result.skeleton_text
    assert "10 - 6 кв" in result.skeleton_text


def test_determinism_versions_and_immutability_are_public_contract() -> None:
    first = build_semantic_skeleton("Труба Ду50 PN16, материал: сталь")
    second = build_semantic_skeleton("Труба Ду50 PN16, материал: сталь")

    assert first == second
    assert first.version == SEMANTIC_SKELETON_VERSION
    assert first.typed_slots_version == "TypedSlots-1.0"
    assert first.canonicalization_version == "TermCanonicalization-2.0"
    with pytest.raises(FrozenInstanceError):
        first.skeleton_text = "changed"  # type: ignore[misc]


def test_skeleton_composes_wave1_scoped_ontology_canonicalization() -> None:
    scoped = build_semantic_skeleton("Монтаж КС", category="electrical", object_kind="cable")
    unscoped = build_semantic_skeleton("Монтаж КС", category=None, object_kind="cable")

    assert scoped.semantic_text == "монтаж cable"
    assert scoped.skeleton_text == "монтаж cable"
    assert unscoped.semantic_text == "монтаж кс"


def test_masking_uses_structural_placeholders_that_cannot_collide_with_user_text() -> None:
    result = build_semantic_skeleton("slotplaceholder0x; марка: ВВГ")

    assert result.skeleton_text == "slotplaceholder0x <brand>"
    assert result.skeleton_text.count("<brand>") == 1


def test_semantic_skeleton_exposes_typed_slot_conflicts_exactly() -> None:
    hints = __import__("typing").get_type_hints(SemanticSkeleton)

    from report_processor.work_semantics.typed_slots import SlotConflict

    assert hints["conflicts"] == tuple[SlotConflict, ...]
