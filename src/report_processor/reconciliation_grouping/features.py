"""Pure deterministic feature extraction for Russian reconciliation work names."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from .models import (
    FEATURE_CONTRACT_VERSION,
    FEATURE_RULE_VERSION,
    FeatureVector,
    GroupInput,
    UnitFamily,
)

_SPACE = re.compile(r"\s+")
_PUNCTUATION = re.compile(r"[^\w№]+", re.UNICODE)
_TOKEN = re.compile(r"[\w№]+", re.UNICODE)
_DN = re.compile(r"\bdn\s*(\d+(?:[.,]\d+)?)\b", re.IGNORECASE)
_KV = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*кв\b", re.IGNORECASE)
_MM = re.compile(r"\b(?:d|диаметр)\s*(\d+(?:[.,]\d+)?)\s*мм\b", re.IGNORECASE)

_ACTION_RULES = {
    "installation": ("монтаж", "монтир", "установк"),
    "laying": ("прокладк", "укладк"),
    "welding": ("сварк",),
    "concreting": ("бетонир",),
    "supply": ("поставк", "поставка"),
    "testing": ("испытан", "пусконалад", "наладк"),
    "dismantling": ("демонтаж", "разборк"),
    "fabrication": ("изготовлен",),
    "supervision": ("надзор",),
}
_OBJECT_RULES = {
    "cable": ("кабел", "провод"),
    "pipeline": ("трубопровод", "труба"),
    "metal_structure": ("металлоконструк",),
    "foundation": ("фундамент",),
    "equipment": ("оборудован",),
}
_CRITICAL_RULES = {
    "power": ("силов",),
    "low_current": ("слаботоч",),
    "reinforced_concrete": ("железобетон", "жб"),
    "dismantling": ("демонтаж",),
    "testing": ("испытан", "пусконалад"),
    "cost": ("стоимост", "цен", "расценк"),
    "supply": ("поставк",),
    "fabrication": ("изготовлен",),
    "supervision": ("надзор",),
}
_NEGATIVE_RULES = {
    "testing": ("испытан", "пусконалад"),
    "cost": ("стоимост", "цен", "расценк"),
    "dismantling": ("демонтаж",),
    "supervision": ("надзор",),
}
_UNIT_ALIASES = {
    UnitFamily.COUNT: frozenset({"шт", "штука", "комплект", "ед"}),
    UnitFamily.LENGTH: frozenset({"м", "метр", "пм", "км"}),
    UnitFamily.AREA: frozenset({"м2", "м²", "квм", "квадратныйметр"}),
    UnitFamily.VOLUME: frozenset({"м3", "м³", "кубм", "кубическийметр"}),
    UnitFamily.MASS: frozenset({"кг", "т", "тонна"}),
}


def normalize_text(value: str | None) -> str:
    """Apply the stable text normalization used by this feature contract."""
    value = unicodedata.normalize("NFKC", value or "").casefold().replace("ё", "е")
    return _SPACE.sub(" ", _PUNCTUATION.sub(" ", value)).strip()


def unit_family(unit: str | None) -> UnitFamily:
    normalized = normalize_unit(unit)
    for family, aliases in _UNIT_ALIASES.items():
        if normalized in aliases:
            return family
    return UnitFamily.UNKNOWN


def normalize_unit(unit: str | None) -> str:
    """Return the exact normalized unit token used for conservative comparison."""
    return normalize_text(unit).replace(" ", "")


def extract_features(
    item: GroupInput,
    *,
    feature_contract_version: str = FEATURE_CONTRACT_VERSION,
    rule_version: str = FEATURE_RULE_VERSION,
) -> FeatureVector:
    """Extract conservative semantic fields; no model result can alter them."""
    normalized_name = normalize_text(item.group.normalized_name)
    tokens = tuple(_TOKEN.findall(normalized_name))
    return FeatureVector(
        group_id=item.group.group_id,
        group_version=item.group.version,
        normalized_name=normalized_name,
        category=item.group.proposed_category,
        mode=item.mode,
        action=_first_match(tokens, _ACTION_RULES),
        object_kind=_first_match(tokens, _OBJECT_RULES),
        critical_modifiers=_matches(tokens, _CRITICAL_RULES),
        negative_markers=_matches(tokens, _NEGATIVE_RULES),
        typed_modifiers=_typed_modifiers(normalized_name),
        unit_family=unit_family(item.group.normalized_unit),
        token_ngrams=_character_ngrams(normalized_name),
        feature_contract_version=feature_contract_version,
        rule_version=rule_version,
    )


def extract_all(
    items: Iterable[GroupInput],
    *,
    feature_contract_version: str = FEATURE_CONTRACT_VERSION,
    rule_version: str = FEATURE_RULE_VERSION,
) -> tuple[FeatureVector, ...]:
    return tuple(
        sorted(
            (
                extract_features(
                    item,
                    feature_contract_version=feature_contract_version,
                    rule_version=rule_version,
                )
                for item in items
            ),
            key=lambda feature: feature.group_id,
        )
    )


def _first_match(tokens: tuple[str, ...], rules: dict[str, tuple[str, ...]]) -> str | None:
    matches = _matches(tokens, rules)
    return matches[0] if matches else None


def _matches(tokens: tuple[str, ...], rules: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    return tuple(
        name
        for name, stems in rules.items()
        if any(any(token.startswith(stem) for stem in stems) for token in tokens)
    )


def _typed_modifiers(normalized_name: str) -> tuple[str, ...]:
    values: list[str] = []
    for prefix, pattern in (("diameter_dn", _DN), ("voltage_kv", _KV), ("diameter_mm", _MM)):
        for match in pattern.finditer(normalized_name):
            values.append(f"{prefix}:{match.group(1).replace(',', '.')}")
    return tuple(sorted(set(values)))


def _character_ngrams(value: str) -> tuple[str, ...]:
    compact = value.replace(" ", "")
    if len(compact) < 3:
        return (compact,) if compact else ()
    return tuple(sorted({compact[index : index + 3] for index in range(len(compact) - 2)}))
