"""Resource-backed domain labels and conservative unit identity."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from importlib.resources import files
from typing import Any, Literal

from .canonicalization import normalize_semantic_text

DOMAIN_ONTOLOGY_VERSION = "DomainOntology-1.0"
UNIT_ONTOLOGY_VERSION = "UnitOntology-1.0"
_WORD = re.compile(r"\w+", re.UNICODE)
_SCHEMA_VERSION = "WorkSemanticsOntology-1.0"


@dataclass(frozen=True, slots=True)
class SemanticConflict:
    kind: Literal["action", "object"]
    labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SemanticLabels:
    primary_action: str | None
    secondary_actions: tuple[str, ...]
    primary_object: str | None
    secondary_objects: tuple[str, ...]
    conflicts: tuple[SemanticConflict, ...]
    version: str = DOMAIN_ONTOLOGY_VERSION


@dataclass(frozen=True, slots=True)
class UnitIdentity:
    canonical_unit: str
    family: str
    scale: Decimal | None
    aliases: tuple[str, ...]
    forbidden_conversions: frozenset[str]
    exact_only: bool
    version: str = UNIT_ONTOLOGY_VERSION


class DomainOntology:
    """Immutable ontology loaded from its sole versioned JSON resource."""

    def __init__(self, payload: dict[str, Any]) -> None:
        _validate_payload(payload)
        self._payload = payload
        self.version = payload["domain_version"]
        self.unit_version = payload["unit_version"]
        self._conflict_pairs = {
            kind: tuple(frozenset(pair) for pair in payload["conflict_pairs"][kind])
            for kind in ("action", "object")
        }

    @classmethod
    def load_default(cls) -> DomainOntology:
        resource = files("report_processor.work_semantics.resources").joinpath(
            "domain_ontology.json"
        )
        return cls(json.loads(resource.read_text(encoding="utf-8")))

    def canonicalize_text(
        self, text: str, *, category: str | None = None, object_kind: str | None = None
    ) -> str:
        tokens = text.split()
        category_key = normalize_semantic_text(category) if category else None
        for rule in self._payload.get("scoped_aliases", []):
            if category_key not in rule.get("categories", []):
                continue
            if rule["kind"] == "object" and object_kind and object_kind != rule["canonical"]:
                continue
            alias = tuple(normalize_semantic_text(rule["alias"]).split())
            tokens = _replace_phrase(tokens, alias, rule["canonical"])
        return " ".join(self._repair_long_token(token) for token in tokens)

    def labels(self, text: str, *, category: str | None = None) -> SemanticLabels:
        normalized = self.canonicalize_text(normalize_semantic_text(text), category=category)
        tokens = tuple(_WORD.findall(normalized))
        actions = self._matches(tokens, self._payload["actions"])
        objects = self._matches(tokens, self._payload["objects"])
        return SemanticLabels(
            primary_action=actions[0] if actions else None,
            secondary_actions=actions[1:],
            primary_object=objects[0] if objects else None,
            secondary_objects=objects[1:],
            conflicts=tuple(
                conflict
                for conflict in (
                    self._conflict("action", actions),
                    self._conflict("object", objects),
                )
                if conflict is not None
            ),
        )

    def unit_identity(self, value: str | None) -> UnitIdentity:
        normalized = _normalize_unit_identity(value)
        for canonical, entry in self._payload["units"].items():
            aliases = tuple(_normalize_unit_identity(alias) for alias in entry["aliases"])
            if normalized in aliases:
                return UnitIdentity(
                    canonical,
                    entry["family"],
                    Decimal(entry["scale"]),
                    aliases,
                    frozenset(entry["forbidden_conversions"]),
                    False,
                )
        return UnitIdentity(normalized, "unknown", None, (normalized,), frozenset(), True)

    def units_compatible(
        self, left: str | UnitIdentity | None, right: str | UnitIdentity | None
    ) -> bool:
        left_identity = left if isinstance(left, UnitIdentity) else self.unit_identity(left)
        right_identity = right if isinstance(right, UnitIdentity) else self.unit_identity(right)
        if left_identity.exact_only or right_identity.exact_only:
            return (
                left_identity.exact_only
                and right_identity.exact_only
                and left_identity.canonical_unit == right_identity.canonical_unit
            )
        if (
            right_identity.canonical_unit in left_identity.forbidden_conversions
            or left_identity.canonical_unit in right_identity.forbidden_conversions
        ):
            return False
        return left_identity.family == right_identity.family

    def _matches(self, tokens: tuple[str, ...], entries: dict[str, Any]) -> tuple[str, ...]:
        found: list[tuple[int, str]] = []
        for label, entry in entries.items():
            positions = [
                index
                for index, token in enumerate(tokens)
                if token == label
                or token in entry["aliases"]
                or any(token.startswith(stem) for stem in entry["stems"])
            ]
            positions.extend(_phrase_positions(tokens, entry["phrases"]))
            if positions:
                found.append((min(positions), label))
        return tuple(label for _, label in sorted(found))

    def _conflict(
        self, kind: Literal["action", "object"], labels: tuple[str, ...]
    ) -> SemanticConflict | None:
        # Labels can describe sequential work. Only a reviewed, explicit pair is a conflict.
        for pair in self._conflict_pairs[kind]:
            if pair <= set(labels):
                return SemanticConflict(kind, tuple(label for label in labels if label in pair))
        return None

    def _repair_long_token(self, token: str) -> str:
        if len(token) < 8 or not token.isalpha():
            return token
        candidates = {
            alias
            for group in (self._payload["actions"], self._payload["objects"])
            for entry in group.values()
            for alias in entry["aliases"]
            if len(alias) >= 8 and " " not in alias
        }
        near = [
            candidate for candidate in candidates if _edit_distance_at_most_one(token, candidate)
        ]
        return near[0] if len(near) == 1 else token


def _phrase_positions(tokens: tuple[str, ...], phrases: list[list[str]]) -> list[int]:
    positions: list[int] = []
    for phrase in phrases:
        length = len(phrase)
        positions.extend(
            index
            for index in range(len(tokens) - length + 1)
            if tokens[index : index + length] == tuple(phrase)
        )
    return positions


def _normalize_unit_identity(value: str | None) -> str:
    """Keep separators in an unknown unit's exact identity."""
    return re.sub(r"\s*([/-])\s*", r"\1", normalize_semantic_text(value))


def _replace_phrase(tokens: list[str], phrase: tuple[str, ...], replacement: str) -> list[str]:
    if not phrase:
        return tokens
    result: list[str] = []
    index = 0
    while index < len(tokens):
        if tuple(tokens[index : index + len(phrase)]) == phrase:
            result.append(replacement)
            index += len(phrase)
        else:
            result.append(tokens[index])
            index += 1
    return result


def _validate_payload(payload: dict[str, Any]) -> None:
    """Reject malformed resources before they can change semantic behaviour."""
    _require_mapping(payload, "resource")
    _require_exact_keys(
        payload,
        {
            "schema_version",
            "domain_version",
            "unit_version",
            "actions",
            "objects",
            "scoped_aliases",
            "conflict_pairs",
            "units",
        },
        "resource",
    )
    if payload["schema_version"] != _SCHEMA_VERSION:
        raise ValueError("unsupported ontology schema version")
    if payload["domain_version"] != DOMAIN_ONTOLOGY_VERSION:
        raise ValueError("unsupported domain ontology version")
    if payload["unit_version"] != UNIT_ONTOLOGY_VERSION:
        raise ValueError("unsupported unit ontology version")

    for group_name in ("actions", "objects"):
        group = payload[group_name]
        _require_mapping(group, group_name)
        for label in sorted(group):
            _require_entry(group[label], f"{group_name}.{label}")

    scoped_aliases = payload["scoped_aliases"]
    if not isinstance(scoped_aliases, list):
        raise ValueError("scoped_aliases must be a list")
    for index, rule in enumerate(scoped_aliases):
        path = f"scoped_aliases[{index}]"
        _require_mapping(rule, path)
        _require_exact_keys(rule, {"alias", "canonical", "kind", "categories"}, path)
        if rule["kind"] not in {"action", "object"} or not isinstance(rule["alias"], str):
            raise ValueError(f"invalid {path}")
        if rule["canonical"] not in payload[f"{rule['kind']}s"]:
            raise ValueError(f"unknown canonical label in {path}")
        _require_strings(rule["categories"], f"{path}.categories")

    conflicts = payload["conflict_pairs"]
    _require_mapping(conflicts, "conflict_pairs")
    _require_exact_keys(conflicts, {"action", "object"}, "conflict_pairs")
    for kind in ("action", "object"):
        pairs = conflicts[kind]
        if not isinstance(pairs, list):
            raise ValueError(f"conflict_pairs.{kind} must be a list")
        for pair in pairs:
            _require_strings(pair, f"conflict_pairs.{kind}")
            if (
                len(pair) != 2
                or len(set(pair)) != 2
                or any(label not in payload[f"{kind}s"] for label in pair)
            ):
                raise ValueError(f"invalid conflict_pairs.{kind}")

    units = payload["units"]
    _require_mapping(units, "units")
    for canonical in sorted(units):
        entry = units[canonical]
        _require_mapping(entry, f"units.{canonical}")
        _require_exact_keys(
            entry,
            {"family", "scale", "aliases", "forbidden_conversions"},
            f"units.{canonical}",
        )
        if not isinstance(entry["family"], str) or not isinstance(entry["scale"], str):
            raise ValueError(f"invalid units.{canonical}")
        try:
            Decimal(entry["scale"])
        except Exception as error:
            raise ValueError(f"invalid units.{canonical}.scale") from error
        _require_strings(entry["aliases"], f"units.{canonical}.aliases")
        _require_string_list(
            entry["forbidden_conversions"], f"units.{canonical}.forbidden_conversions"
        )
        if any(target not in units for target in entry["forbidden_conversions"]):
            raise ValueError(f"unknown unit conversion in units.{canonical}")


def _require_mapping(value: Any, path: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")


def _require_exact_keys(value: dict[str, Any], expected: set[str], path: str) -> None:
    if set(value) != expected:
        raise ValueError(f"invalid keys for {path}")


def _require_strings(value: Any, path: str) -> None:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item for item in value)
    ):
        raise ValueError(f"{path} must be a non-empty string list")


def _require_entry(value: Any, path: str) -> None:
    _require_mapping(value, path)
    _require_exact_keys(value, {"aliases", "stems", "phrases"}, path)
    _require_string_list(value["aliases"], f"{path}.aliases")
    _require_string_list(value["stems"], f"{path}.stems")
    if not isinstance(value["phrases"], list):
        raise ValueError(f"{path}.phrases must be a list")
    for phrase in value["phrases"]:
        _require_strings(phrase, f"{path}.phrases")
    if not (value["aliases"] or value["stems"] or value["phrases"]):
        raise ValueError(f"{path} must have a matcher")


def _require_string_list(value: Any, path: str) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{path} must be a string list")


def _edit_distance_at_most_one(left: str, right: str) -> bool:
    if abs(len(left) - len(right)) > 1:
        return False
    if left == right:
        return True
    if len(left) == len(right):
        return sum(a != b for a, b in zip(left, right, strict=True)) == 1
    shorter, longer = sorted((left, right), key=len)
    index = mismatch = 0
    while index < len(shorter):
        if shorter[index] != longer[index + mismatch]:
            mismatch += 1
            if mismatch > 1:
                return False
            continue
        index += 1
    return True


DEFAULT_ONTOLOGY = DomainOntology.load_default()


def extract_semantic_labels(text: str, *, category: str | None = None) -> SemanticLabels:
    return DEFAULT_ONTOLOGY.labels(text, category=category)


def canonical_unit(value: str | None) -> UnitIdentity:
    return DEFAULT_ONTOLOGY.unit_identity(value)


def units_compatible(left: str | UnitIdentity | None, right: str | UnitIdentity | None) -> bool:
    return DEFAULT_ONTOLOGY.units_compatible(left, right)
