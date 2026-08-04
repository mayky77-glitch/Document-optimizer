from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal
from typing import get_type_hints

import pytest

from report_processor.work_semantics.typed_slots import (
    TYPED_SLOTS_VERSION,
    CableSectionValue,
    DiameterValue,
    RangeValue,
    ScalarValue,
    SlotConflict,
    SlotImpact,
    SlotKind,
    TextValue,
    TypedSlotParse,
    parse_typed_slots,
)


def _by_kind(parsed, kind: SlotKind):
    return tuple(slot for slot in parsed.slots if slot.kind is kind)


@pytest.mark.parametrize(
    ("source", "expected", "basis"),
    [
        ("Труба DN50", Decimal("50"), "nominal"),
        ("Труба Ду 50", Decimal("50"), "nominal"),
        ("Труба ДН50", Decimal("50"), "nominal"),
        ("Труба Ø57 мм", Decimal("57"), "outer"),
        ("Труба диаметр 57 мм", Decimal("57"), "unspecified"),
    ],
)
def test_diameter_forms_are_decimal_family_boundaries(
    source: str, expected: Decimal, basis: str
) -> None:
    slot = _by_kind(parse_typed_slots(source), SlotKind.DIAMETER)[0]

    assert slot.impact is SlotImpact.FAMILY_BOUNDARY
    assert isinstance(slot.value, DiameterValue)
    assert slot.value.mm == expected
    assert slot.value.basis == basis
    assert slot.normalized == f"{basis}:{expected}:mm"


def test_ambiguous_diameter_is_not_extracted_outside_object_scope() -> None:
    parsed = parse_typed_slots("Монтаж D57", object_kind=None)

    assert not _by_kind(parsed, SlotKind.DIAMETER)
    assert [warning.code for warning in parsed.warnings] == ["ambiguous_diameter"]
    assert parsed.requires_manual_review


@pytest.mark.parametrize(("source", "normalized"), [("PN16", "16:pn"), ("Ру 16", "16:pn")])
def test_pressure_homographs_are_equivalent(source: str, normalized: str) -> None:
    slot = _by_kind(parse_typed_slots(source), SlotKind.PRESSURE)[0]

    assert slot.impact is SlotImpact.FAMILY_BOUNDARY
    assert isinstance(slot.value, ScalarValue)
    assert slot.value.value == Decimal("16")
    assert slot.value.unit == "pn"
    assert slot.normalized == normalized


def test_voltage_supports_scalar_and_range_and_rejects_reversed_range() -> None:
    parsed = parse_typed_slots("Кабель 0,4 кВ и 6–10 кВ")
    scalar, interval = _by_kind(parsed, SlotKind.VOLTAGE)

    assert isinstance(scalar.value, ScalarValue)
    assert scalar.value.value == Decimal("0.4")
    assert scalar.normalized == "0.4:kv"
    assert isinstance(interval.value, RangeValue)
    assert (interval.value.lower, interval.value.upper, interval.value.unit) == (
        Decimal("6"),
        Decimal("10"),
        "kv",
    )
    assert interval.normalized == "6..10:kv"

    invalid = parse_typed_slots("Кабель 10-6 кВ")
    assert "invalid_range" in [warning.code for warning in invalid.warnings]
    assert not _by_kind(invalid, SlotKind.VOLTAGE)


@pytest.mark.parametrize(
    ("source", "cores", "section"), [("4×16 мм²", 4, "16"), ("3х2,5 мм2", 3, "2.5")]
)
def test_cable_section_is_context_scoped_and_decimal(source: str, cores: int, section: str) -> None:
    slot = _by_kind(parse_typed_slots(source, object_kind="cable"), SlotKind.CABLE_SECTION)[0]

    assert slot.impact is SlotImpact.FAMILY_BOUNDARY
    assert isinstance(slot.value, CableSectionValue)
    assert (slot.value.cores, slot.value.section_mm2) == (cores, Decimal(section))
    assert slot.normalized == f"{cores}x{Decimal(section)}:mm2"

    ambiguous = parse_typed_slots(source.split()[0], object_kind="pipeline")
    assert not _by_kind(ambiguous, SlotKind.CABLE_SECTION)
    assert "ambiguous_cable_section" in [item.code for item in ambiguous.warnings]


def test_length_mass_and_count_normalize_without_merging_piece_and_set() -> None:
    parsed = parse_typed_slots("2000 м; 1,5 т; 3 шт; 2 компл")
    length = _by_kind(parsed, SlotKind.LENGTH)[0]
    mass = _by_kind(parsed, SlotKind.MASS)[0]
    count = _by_kind(parsed, SlotKind.COUNT)

    assert (length.value.value, length.value.unit, length.normalized) == (
        Decimal("2000"),
        "m",
        "2000:m",
    )
    assert (mass.value.value, mass.value.unit, mass.normalized) == (
        Decimal("1500"),
        "kg",
        "1500:kg",
    )
    assert [(slot.value.value, slot.value.unit) for slot in count] == [
        (Decimal("3"), "piece"),
        (Decimal("2"), "set"),
    ]
    assert {slot.impact for slot in (length, mass, *count)} == {SlotImpact.CATEGORY_NEUTRAL}


@pytest.mark.parametrize(
    ("source", "kind", "normalized", "impact"),
    [
        ("марка: ВВГнг-LS", SlotKind.BRAND, "ввгнг-ls", SlotImpact.FAMILY_BOUNDARY),
        ("материал: сталь", SlotKind.MATERIAL, "сталь", SlotImpact.HARD_CONFLICT),
        ("исполнение: УХЛ1", SlotKind.EXECUTION, "ухл1", SlotImpact.FAMILY_BOUNDARY),
        ("ГОСТ 123-45", SlotKind.GOST, "гост:123-45", SlotImpact.FAMILY_BOUNDARY),
        ("ТУ 12.34", SlotKind.TU, "ту:12.34", SlotImpact.FAMILY_BOUNDARY),
        ("класс огнестойкости: E30", SlotKind.FIRE_CLASS, "e30", SlotImpact.HARD_CONFLICT),
        ("модель: ABC-10", SlotKind.MODEL, "abc-10", SlotImpact.FAMILY_BOUNDARY),
        ("артикул: 12-AB", SlotKind.ARTICLE, "12-ab", SlotImpact.FAMILY_BOUNDARY),
        ("индекс документа: 1006-01", SlotKind.DOCUMENT_INDEX, "1006-01", SlotImpact.DISPLAY_ONLY),
    ],
)
def test_explicit_text_slots_have_fixed_kind_impact_and_normalization(
    source, kind, normalized, impact
) -> None:
    slot = _by_kind(parse_typed_slots(source), kind)[0]

    assert isinstance(slot.value, TextValue)
    assert (slot.normalized, slot.value.value, slot.impact) == (normalized, normalized, impact)


def test_audit_spans_are_exact_code_point_slices_and_outputs_are_immutable() -> None:
    parsed = parse_typed_slots("Ёлка; Ду50; 0,4 кВ")

    assert parsed.version == TYPED_SLOTS_VERSION
    assert all(
        slot.audit_fragment == parsed.audit_text[slot.span.start : slot.span.end]
        for slot in parsed.slots
    )
    with pytest.raises(FrozenInstanceError):
        parsed.audit_text = "changed"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        parsed.slots.append(None)  # type: ignore[attr-defined]


def test_overlap_precedence_protects_diameter_cable_and_standard_numbers() -> None:
    parsed = parse_typed_slots("D50 мм; 4×16 мм²; ГОСТ 123-45", object_kind="pipeline")

    assert [slot.kind for slot in parsed.slots] == [
        SlotKind.DIAMETER,
        SlotKind.CABLE_SECTION,
        SlotKind.GOST,
    ]
    assert not _by_kind(parsed, SlotKind.LENGTH)
    assert not _by_kind(parsed, SlotKind.COUNT)


def test_conflicts_and_multiple_family_values_are_stable_and_manual() -> None:
    material = parse_typed_slots("материал: сталь; материал: медь")
    diameters = parse_typed_slots("DN50 DN80")

    assert [conflict.code for conflict in material.conflicts] == ["conflicting_material"]
    assert material.requires_manual_review
    assert [warning.code for warning in diameters.warnings] == ["multiple_family_values"]
    assert diameters.requires_manual_review


@pytest.mark.parametrize(
    ("source", "kind", "normalized"),
    [
        ("документ № 123", SlotKind.DOCUMENT_INDEX, "123"),
        ("документ No 123", SlotKind.DOCUMENT_INDEX, "123"),
        ("ГОСТ123-45", SlotKind.GOST, "гост:123-45"),
        ("ГОСТ 123-45", SlotKind.GOST, "гост:123-45"),
        ("ТУ12.34", SlotKind.TU, "ту:12.34"),
        ("ТУ 12.34", SlotKind.TU, "ту:12.34"),
    ],
)
def test_numero_nfkc_and_compact_or_spaced_standards_are_safe(
    source: str, kind: SlotKind, normalized: str
) -> None:
    parsed = parse_typed_slots(source)

    assert [(slot.kind, slot.normalized) for slot in parsed.slots] == [(kind, normalized)]
    assert not parsed.warnings


@pytest.mark.parametrize(
    ("source", "scope", "kind", "normalized"),
    [
        ("Труба D57", "pipeline", SlotKind.DIAMETER, "unspecified:57:mm"),
        ("Труба д 57", "pipeline", SlotKind.DIAMETER, "unspecified:57:mm"),
        ("Кабель 4×16", "cable", SlotKind.CABLE_SECTION, "4x16:mm2"),
    ],
)
def test_bare_dimensions_extract_only_in_the_required_object_scope(
    source: str, scope: str, kind: SlotKind, normalized: str
) -> None:
    parsed = parse_typed_slots(source, object_kind=scope)

    assert [(slot.kind, slot.normalized) for slot in parsed.slots] == [(kind, normalized)]
    assert not parsed.warnings


@pytest.mark.parametrize(
    ("source", "warning"),
    [
        ("DN", "missing_slot_value"),
        ("PN x", "invalid_numeric_value"),
        ("марка:", "missing_slot_value"),
        ("материал: ;", "missing_slot_value"),
        ("ГОСТ", "missing_slot_value"),
    ],
)
def test_malformed_explicit_markers_stay_literal_and_require_manual_review(
    source: str, warning: str
) -> None:
    parsed = parse_typed_slots(source)

    assert not parsed.slots
    assert [item.code for item in parsed.warnings] == [warning]
    assert parsed.requires_manual_review


@pytest.mark.parametrize(
    ("source", "scope", "warning", "fragment"),
    [
        ("10-x кВ", None, "invalid_numeric_value", "10-x кВ"),
        ("10- кВ", None, "invalid_numeric_value", "10- кВ"),
        ("Труба D x", "pipeline", "invalid_numeric_value", "D x"),
        ("Кабель 4x мм2", "cable", "invalid_numeric_value", "4x мм2"),
    ],
)
def test_malformed_numeric_slots_fail_closed_with_exact_audit_spans(
    source: str, scope: str | None, warning: str, fragment: str
) -> None:
    parsed = parse_typed_slots(source, object_kind=scope)

    assert not parsed.slots
    assert [
        (item.code, parsed.audit_text[item.span.start : item.span.end]) for item in parsed.warnings
    ] == [(warning, fragment)]
    assert parsed.requires_manual_review


@pytest.mark.parametrize(
    ("source", "scope"),
    [
        ("Диаметр трубы принят по проекту", "pipeline"),
        ("Кабель проложен в лотке", "cable"),
        ("Труба D57", "pipeline"),
        ("Кабель 4x16 мм2", "cable"),
    ],
)
def test_malformed_numeric_scanners_do_not_warn_on_prose_or_valid_slots(
    source: str, scope: str
) -> None:
    parsed = parse_typed_slots(source, object_kind=scope)

    assert not parsed.warnings


def test_public_models_and_annotations_freeze_decimal_and_conflict_contract() -> None:
    parse_hints = get_type_hints(parse_typed_slots)
    assert parse_hints["value"] is object
    assert parse_hints["return"] is TypedSlotParse
    assert get_type_hints(CableSectionValue)["cores"] is Decimal
    assert get_type_hints(TypedSlotParse)["conflicts"] == tuple[SlotConflict, ...]

    section = CableSectionValue(Decimal("4"), Decimal("16"))
    assert section.cores == Decimal("4")
    with pytest.raises((TypeError, ValueError)):
        CableSectionValue(4, Decimal("16"))  # type: ignore[arg-type]
