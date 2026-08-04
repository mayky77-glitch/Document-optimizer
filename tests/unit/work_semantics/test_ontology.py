from __future__ import annotations

import copy
import json
from decimal import Decimal
from importlib.resources import files

import pytest

from report_processor.work_semantics import (
    DEFAULT_ONTOLOGY,
    DOMAIN_ONTOLOGY_VERSION,
    UNIT_ONTOLOGY_VERSION,
    canonical_unit,
    canonicalize_term,
    extract_semantic_labels,
    units_compatible,
)
from report_processor.work_semantics.ontology import DomainOntology


@pytest.mark.parametrize(
    ("text", "expected_action", "expected_object"),
    [
        ("Прокладываем кабели", "laying", "cable"),
        ("Сварить трубопровод", "welding", "pipeline"),
        ("Бетонирование фундамента", "concreting", "foundation"),
        ("Поставка оборудования", "supply", "equipment"),
        ("Испытать автоматику", "testing", "automation"),
        ("Демонтировать опору", "dismantling", "support"),
        ("Изготовить металлоконструкцию", "fabrication", "metal_structure"),
        ("Надзор за освещением", "supervision", "lighting"),
        ("Окраска покрытия", "painting", "coating"),
        ("Изолировать муфту", "insulation", "coupling"),
        ("Очистить лоток", "cleaning", "tray"),
        ("Земляные работы для заземления", "earthworks", "grounding"),
        ("Транспортировка арматуры", "transportation", "reinforcement"),
        ("Подключить провод", "connection", "cable"),
        ("Пусконаладка оборудования", "commissioning", "equipment"),
    ],
)
def test_ontology_covers_required_actions_and_objects(
    text: str, expected_action: str, expected_object: str
) -> None:
    labels = extract_semantic_labels(text)

    assert labels.primary_action == expected_action
    assert labels.primary_object == expected_object
    assert labels.version == DOMAIN_ONTOLOGY_VERSION


def test_scoped_alias_and_multiword_alias_are_only_resolved_in_their_scope() -> None:
    electrical = canonicalize_term("Монтаж КС", category="electrical", ontology=DEFAULT_ONTOLOGY)
    unscoped = canonicalize_term("Монтаж КС", ontology=DEFAULT_ONTOLOGY)
    labels = extract_semantic_labels("Монтаж КС", category="electrical")

    assert electrical.semantic_text == "монтаж cable"
    assert unscoped.semantic_text == "монтаж кс"
    assert labels.primary_action == "installation"
    assert labels.primary_object == "cable"
    assert labels.secondary_objects == ()


def test_typo_repair_is_conservative_at_the_long_token_boundary() -> None:
    repaired = canonicalize_term("транспортировкя", ontology=DEFAULT_ONTOLOGY)
    short = canonicalize_term("монтащ", ontology=DEFAULT_ONTOLOGY)
    distant = canonicalize_term("транспортировкxyz", ontology=DEFAULT_ONTOLOGY)

    assert repaired.semantic_text == "транспортировка"
    assert short.semantic_text == "монтащ"
    assert distant.semantic_text == "транспортировкxyz"


def test_multi_action_and_object_labels_are_ordered_and_conflicts_are_explicit() -> None:
    labels = extract_semantic_labels("Монтаж и демонтаж кабеля и лотка")

    assert labels.primary_action == "installation"
    assert labels.secondary_actions == ("dismantling",)
    assert labels.primary_object == "cable"
    assert labels.secondary_objects == ("tray",)
    assert labels.conflicts[0].kind == "action"
    assert labels.conflicts[0].labels == ("installation", "dismantling")


def test_supply_and_installation_are_not_presumed_to_conflict() -> None:
    labels = extract_semantic_labels("Поставка и монтаж оборудования")

    assert labels.primary_action == "supply"
    assert labels.secondary_actions == ("installation",)
    assert labels.conflicts == ()


@pytest.mark.parametrize(
    ("value", "canonical", "family", "scale"),
    [
        ("шт.", "piece", "count", Decimal("1")),
        ("компл.", "set", "count", Decimal("1")),
        ("кв м", "square_meter", "area", Decimal("1")),
        ("кубический метр", "cubic_meter", "volume", Decimal("1")),
        ("тонны", "tonne", "mass", Decimal("1000")),
    ],
)
def test_unit_identity_exposes_alias_family_and_scale(
    value: str, canonical: str, family: str, scale: Decimal
) -> None:
    identity = canonical_unit(value)

    assert identity.canonical_unit == canonical
    assert identity.family == family
    assert identity.scale == scale
    assert not identity.exact_only
    assert identity.version == UNIT_ONTOLOGY_VERSION


def test_units_keep_piece_and_set_incompatible_while_scaled_families_are_compatible() -> None:
    assert not units_compatible("шт", "комплект")
    assert units_compatible("м", "км")
    assert units_compatible("кг", "т")


def test_unknown_units_are_exact_only_and_cannot_broadly_merge() -> None:
    unknown = canonical_unit("условная единица")

    assert unknown.exact_only
    assert unknown.family == "unknown"
    assert units_compatible("условная единица", "условная единица")
    assert not units_compatible("условная единица", "условная ед.")
    assert not units_compatible("условная единица", "шт")


def test_unknown_unit_separators_and_unlisted_spaces_remain_exact_identity() -> None:
    slash = canonical_unit("пакет/смена")
    spaced = canonical_unit("пакет смена")
    collapsed = canonical_unit("пакетсмена")

    assert slash.canonical_unit != spaced.canonical_unit
    assert spaced.canonical_unit != collapsed.canonical_unit
    assert not units_compatible(slash, spaced)
    assert not units_compatible(spaced, collapsed)


def test_phrase_alias_is_matched_but_a_ground_category_is_not_earthworks() -> None:
    phrase = extract_semantic_labels("Земляные работы для заземления")
    category = extract_semantic_labels("Грунт категории II")

    assert phrase.primary_action == "earthworks"
    assert phrase.primary_object == "grounding"
    assert category.primary_action is None


def test_json_resource_owns_versions_conflicts_and_rejects_invalid_schema() -> None:
    resource = files("report_processor.work_semantics.resources").joinpath("domain_ontology.json")
    payload = json.loads(resource.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "WorkSemanticsOntology-1.0"
    assert payload["domain_version"] == DOMAIN_ONTOLOGY_VERSION
    assert payload["unit_version"] == UNIT_ONTOLOGY_VERSION
    assert payload["conflict_pairs"] == {
        "action": [["installation", "dismantling"]],
        "object": [],
    }

    missing_units = copy.deepcopy(payload)
    del missing_units["units"]
    with pytest.raises(ValueError):
        DomainOntology(missing_units)

    unknown_conflict_label = copy.deepcopy(payload)
    unknown_conflict_label["conflict_pairs"]["action"] = [["installation", "not-an-action"]]
    with pytest.raises(ValueError):
        DomainOntology(unknown_conflict_label)
