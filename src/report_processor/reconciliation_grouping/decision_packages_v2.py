"""Inert, privacy-safe DTOs for constrained reconciliation decision packages.

This module intentionally has no runtime imports from the legacy grouping flow.
It carries opaque references and controlled enumerations only; it never carries
source terms, feature vectors, source locations, or scores.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, fields, is_dataclass
from enum import StrEnum
from itertools import combinations
from typing import Any

DECISION_PACKAGE_VERSION = "DecisionPackage-2.0"
MAX_ATOMS_PER_FAMILY = 128
MAX_FAMILIES_PER_PACKAGE = 64
MAX_PACKAGES_PER_RESULT = 512
MAX_PAIR_CONSTRAINTS_PER_PACKAGE = 8_192

_SHA_REF = re.compile(r"sha256:[0-9a-f]{64}\Z")
_VERSION = re.compile(r"[A-Za-z][A-Za-z0-9_-]*-\d+\.\d+\Z")


class DecisionPackageContractError(ValueError):
    """Controlled invariant failure without echoing restricted input values."""


class PackageMode(StrEnum):
    QUANTITY_COST = "quantity_cost"
    COST_ONLY = "cost_only"


class UnitCompatibility(StrEnum):
    COMPATIBLE = "compatible"
    EXACT_ONLY = "exact_only"
    UNKNOWN = "unknown"
    INCOMPATIBLE = "incompatible"


class PairRelation(StrEnum):
    MUST_LINK = "must_link"
    CANNOT_LINK = "cannot_link"
    MANUAL_REVIEW = "manual_review"


def canonical_json_bytes(value: object) -> bytes:
    """Return deterministic JSON bytes for the closed set of contract values."""
    try:
        return json.dumps(
            _canonical_value(value),
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as error:
        raise DecisionPackageContractError("canonical contract value required") from error


def sha256_fingerprint(value: object) -> str:
    """Return the canonical SHA-256 fingerprint for a contract value."""
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _canonical_value(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _canonical_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple):
        return [_canonical_value(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise DecisionPackageContractError("canonical mappings require string keys")
        return {key: _canonical_value(item) for key, item in value.items()}
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    # bool is handled above and floats are intentionally never contract values.
    raise DecisionPackageContractError("unsupported contract value")


def _require_sha_ref(value: str, *, field_name: str) -> None:
    if not isinstance(value, str) or not _SHA_REF.fullmatch(value):
        raise DecisionPackageContractError(f"{field_name} must be an opaque sha256 reference")


def _require_version(value: str, *, field_name: str) -> None:
    if not isinstance(value, str) or not _VERSION.fullmatch(value):
        raise DecisionPackageContractError(f"{field_name} must be a controlled version")


def _opaque_id(kind: str, fingerprint: str) -> str:
    _require_sha_ref(fingerprint, field_name="fingerprint")
    return f"{kind}-{fingerprint.removeprefix('sha256:')}"


def _canonical_tuple(values: tuple[Any, ...], *, key: Any, label: str) -> tuple[Any, ...]:
    if len(values) != len({key(value) for value in values}):
        raise DecisionPackageContractError(f"{label} must be unique")
    return tuple(sorted(values, key=key))


@dataclass(frozen=True, slots=True)
class PackageBoundary:
    """Controlled outcome boundary for atoms, families, and packages."""

    category_ref: str | None
    mode: PackageMode | None
    unit_compatibility: UnitCompatibility
    action_ref: str | None
    object_ref: str | None

    def __post_init__(self) -> None:
        if self.mode is not None and not isinstance(self.mode, PackageMode):
            raise DecisionPackageContractError("mode must be controlled")
        if not isinstance(self.unit_compatibility, UnitCompatibility):
            raise DecisionPackageContractError("unit compatibility must be controlled")
        for name, value in (
            ("category_ref", self.category_ref),
            ("action_ref", self.action_ref),
            ("object_ref", self.object_ref),
        ):
            if value is not None:
                _require_sha_ref(value, field_name=name)

    @property
    def is_known(self) -> bool:
        return (
            self.category_ref is not None
            and self.mode is not None
            and self.action_ref is not None
            and self.object_ref is not None
        )

    @property
    def fingerprint(self) -> str:
        return sha256_fingerprint(
            {"version": DECISION_PACKAGE_VERSION, "kind": "boundary", "value": self}
        )


@dataclass(frozen=True, slots=True)
class PackageAtom:
    """One opaque semantic identity and its controlled package boundary."""

    semantic_ref: str
    boundary: PackageBoundary
    version: str = DECISION_PACKAGE_VERSION

    def __post_init__(self) -> None:
        _require_sha_ref(self.semantic_ref, field_name="semantic_ref")
        if not isinstance(self.boundary, PackageBoundary):
            raise DecisionPackageContractError("atom boundary must be controlled")
        if self.version != DECISION_PACKAGE_VERSION:
            raise DecisionPackageContractError("atom version must bind DecisionPackage-2.0")

    @property
    def fingerprint(self) -> str:
        return sha256_fingerprint(
            {
                "version": self.version,
                "kind": "atom",
                "semantic_ref": self.semantic_ref,
                "boundary": self.boundary,
            }
        )

    @property
    def atom_id(self) -> str:
        return _opaque_id("package-atom", self.fingerprint)


@dataclass(frozen=True, slots=True)
class PairConstraint:
    """Canonical complete-linkage relation for one pair of opaque atoms."""

    left_atom_id: str
    right_atom_id: str
    relation: PairRelation
    version: str = DECISION_PACKAGE_VERSION

    def __post_init__(self) -> None:
        if self.version != DECISION_PACKAGE_VERSION:
            raise DecisionPackageContractError(
                "pair constraint version must bind DecisionPackage-2.0"
            )
        if not self.left_atom_id.startswith("package-atom-") or not self.right_atom_id.startswith(
            "package-atom-"
        ):
            raise DecisionPackageContractError("pair constraints require opaque atom IDs")
        if self.left_atom_id == self.right_atom_id:
            raise DecisionPackageContractError("pair constraints cannot be self-referential")
        if not isinstance(self.relation, PairRelation):
            raise DecisionPackageContractError("pair relation must be controlled")
        left, right = sorted((self.left_atom_id, self.right_atom_id))
        object.__setattr__(self, "left_atom_id", left)
        object.__setattr__(self, "right_atom_id", right)

    @property
    def pair_key(self) -> tuple[str, str]:
        return (self.left_atom_id, self.right_atom_id)

    @property
    def is_compatible(self) -> bool:
        return self.relation is PairRelation.MUST_LINK

    @property
    def fingerprint(self) -> str:
        return sha256_fingerprint(
            {
                "version": self.version,
                "kind": "pair_constraint",
                "left_atom_id": self.left_atom_id,
                "right_atom_id": self.right_atom_id,
                "relation": self.relation,
            }
        )

    @property
    def constraint_id(self) -> str:
        return _opaque_id("pair-constraint", self.fingerprint)


@dataclass(frozen=True, slots=True)
class CandidateFamily:
    """A bounded, canonical family before bounded package selection."""

    atoms: tuple[PackageAtom, ...]
    pair_constraints: tuple[PairConstraint, ...] = ()
    manual_review_required: bool = False
    version: str = DECISION_PACKAGE_VERSION

    def __post_init__(self) -> None:
        if self.version != DECISION_PACKAGE_VERSION:
            raise DecisionPackageContractError(
                "candidate family version must bind DecisionPackage-2.0"
            )
        if not self.atoms or len(self.atoms) > MAX_ATOMS_PER_FAMILY:
            raise DecisionPackageContractError("candidate family atom count is out of bounds")
        if not isinstance(self.manual_review_required, bool):
            raise DecisionPackageContractError("candidate manual blocker must be boolean")
        if any(not isinstance(atom, PackageAtom) for atom in self.atoms):
            raise DecisionPackageContractError("candidate atoms must be contract atoms")
        atoms = _canonical_tuple(self.atoms, key=lambda item: item.atom_id, label="candidate atoms")
        object.__setattr__(self, "atoms", atoms)
        if len(self.pair_constraints) > MAX_PAIR_CONSTRAINTS_PER_PACKAGE:
            raise DecisionPackageContractError("candidate pair constraints exceed the bound")
        if any(not isinstance(item, PairConstraint) for item in self.pair_constraints):
            raise DecisionPackageContractError("candidate constraints must be controlled")
        constraints = _canonical_tuple(
            self.pair_constraints,
            key=lambda item: item.pair_key,
            label="candidate pair constraints",
        )
        atom_ids = set(self.atom_ids)
        if any(not set(item.pair_key) <= atom_ids for item in constraints):
            raise DecisionPackageContractError(
                "candidate constraints must reference candidate atoms"
            )
        object.__setattr__(self, "pair_constraints", constraints)

    @property
    def atom_ids(self) -> tuple[str, ...]:
        return tuple(atom.atom_id for atom in self.atoms)

    @property
    def boundary(self) -> PackageBoundary | None:
        boundaries = {atom.boundary for atom in self.atoms}
        return next(iter(boundaries)) if len(boundaries) == 1 else None

    @property
    def has_complete_pair_coverage(self) -> bool:
        expected = {tuple(pair) for pair in combinations(self.atom_ids, 2)}
        return {constraint.pair_key for constraint in self.pair_constraints} == expected

    @property
    def all_pairs_compatible(self) -> bool:
        return all(constraint.is_compatible for constraint in self.pair_constraints)

    @property
    def fingerprint(self) -> str:
        return sha256_fingerprint(
            {
                "version": self.version,
                "kind": "candidate_family",
                "atom_ids": self.atom_ids,
                "pair_constraint_ids": tuple(
                    constraint.constraint_id for constraint in self.pair_constraints
                ),
                "manual_review_required": self.manual_review_required,
            }
        )

    @property
    def family_id(self) -> str:
        return _opaque_id("candidate-family", self.fingerprint)


@dataclass(frozen=True, slots=True)
class OptimizerPolicy:
    """Explicit finite limits for the inert package optimizer."""

    policy_ref: str
    max_safe_atoms: int
    max_families: int
    max_pair_constraints: int
    version: str = "DecisionPackageOptimizerPolicy-1.0"

    def __post_init__(self) -> None:
        _require_sha_ref(self.policy_ref, field_name="policy_ref")
        _require_version(self.version, field_name="policy version")
        if (
            not isinstance(self.max_safe_atoms, int)
            or not isinstance(self.max_families, int)
            or not isinstance(self.max_pair_constraints, int)
            or isinstance(self.max_safe_atoms, bool)
            or isinstance(self.max_families, bool)
            or isinstance(self.max_pair_constraints, bool)
            or not 1 <= self.max_safe_atoms <= MAX_ATOMS_PER_FAMILY
            or not 1 <= self.max_families <= MAX_FAMILIES_PER_PACKAGE
            or not 0 <= self.max_pair_constraints <= MAX_PAIR_CONSTRAINTS_PER_PACKAGE
        ):
            raise DecisionPackageContractError("optimizer policy limits are out of bounds")

    @property
    def fingerprint(self) -> str:
        return sha256_fingerprint({"kind": "optimizer_policy", "value": self})


@dataclass(frozen=True, slots=True)
class DecisionPackageVersionContext:
    """Consequential, controlled versions required to interpret a package."""

    semantic_contract_version: str
    feedback_contract_version: str
    clustering_contract_version: str
    optimizer_policy_version: str
    version: str = DECISION_PACKAGE_VERSION

    def __post_init__(self) -> None:
        if self.version != DECISION_PACKAGE_VERSION:
            raise DecisionPackageContractError("context version must bind DecisionPackage-2.0")
        for name, value in (
            ("semantic_contract_version", self.semantic_contract_version),
            ("feedback_contract_version", self.feedback_contract_version),
            ("clustering_contract_version", self.clustering_contract_version),
            ("optimizer_policy_version", self.optimizer_policy_version),
        ):
            _require_version(value, field_name=name)

    @property
    def fingerprint(self) -> str:
        return sha256_fingerprint({"kind": "version_context", "value": self})


@dataclass(frozen=True, slots=True)
class DecisionPackage:
    """A deterministic package whose ``safe`` status is derived, never asserted."""

    families: tuple[CandidateFamily, ...]
    pair_constraints: tuple[PairConstraint, ...]
    policy: OptimizerPolicy
    version_context: DecisionPackageVersionContext
    version: str = DECISION_PACKAGE_VERSION

    def __post_init__(self) -> None:
        if self.version != DECISION_PACKAGE_VERSION:
            raise DecisionPackageContractError("package version must bind DecisionPackage-2.0")
        if not self.families or len(self.families) > self.policy.max_families:
            raise DecisionPackageContractError("package family count is out of policy bounds")
        if any(not isinstance(item, CandidateFamily) for item in self.families):
            raise DecisionPackageContractError("package families must be contract families")
        families = _canonical_tuple(
            self.families,
            key=lambda item: item.family_id,
            label="package families",
        )
        object.__setattr__(self, "families", families)
        if len(self.pair_constraints) > self.policy.max_pair_constraints:
            raise DecisionPackageContractError("package pair constraints exceed the policy bound")
        if any(not isinstance(item, PairConstraint) for item in self.pair_constraints):
            raise DecisionPackageContractError("package constraints must be controlled")
        constraints = _canonical_tuple(
            self.pair_constraints, key=lambda item: item.pair_key, label="package pair constraints"
        )
        atom_ids = set(self.atom_ids)
        if any(not set(item.pair_key) <= atom_ids for item in constraints):
            raise DecisionPackageContractError("package constraints must reference package atoms")
        object.__setattr__(self, "pair_constraints", constraints)
        if self.policy.version != self.version_context.optimizer_policy_version:
            raise DecisionPackageContractError("policy and version context must agree")

    @property
    def atoms(self) -> tuple[PackageAtom, ...]:
        atoms = tuple(atom for family in self.families for atom in family.atoms)
        if len(atoms) != len({atom.atom_id for atom in atoms}):
            raise DecisionPackageContractError("package atoms must be unique across families")
        return tuple(sorted(atoms, key=lambda item: item.atom_id))

    @property
    def atom_ids(self) -> tuple[str, ...]:
        return tuple(atom.atom_id for atom in self.atoms)

    @property
    def boundary(self) -> PackageBoundary | None:
        boundaries = {atom.boundary for atom in self.atoms}
        return next(iter(boundaries)) if len(boundaries) == 1 else None

    @property
    def has_complete_pair_coverage(self) -> bool:
        expected = {tuple(pair) for pair in combinations(self.atom_ids, 2)}
        return {constraint.pair_key for constraint in self.pair_constraints} == expected

    @property
    def safe(self) -> bool:
        boundary = self.boundary
        return (
            boundary is not None
            and boundary.is_known
            and boundary.unit_compatibility is UnitCompatibility.COMPATIBLE
            and len(self.atoms) <= self.policy.max_safe_atoms
            and not any(family.manual_review_required for family in self.families)
            and all(family.all_pairs_compatible for family in self.families)
            and self.has_complete_pair_coverage
            and all(constraint.is_compatible for constraint in self.pair_constraints)
        )

    @property
    def fingerprint(self) -> str:
        return sha256_fingerprint(
            {
                "version": self.version,
                "kind": "decision_package",
                "family_ids": tuple(family.family_id for family in self.families),
                "pair_constraint_ids": tuple(
                    constraint.constraint_id for constraint in self.pair_constraints
                ),
                "policy_fingerprint": self.policy.fingerprint,
                "version_context_fingerprint": self.version_context.fingerprint,
            }
        )

    @property
    def package_id(self) -> str:
        return _opaque_id("decision-package", self.fingerprint)


@dataclass(frozen=True, slots=True)
class DecisionPackageResult:
    """The inert, ordered package output for one exact policy and context."""

    packages: tuple[DecisionPackage, ...]
    policy: OptimizerPolicy
    version_context: DecisionPackageVersionContext
    version: str = DECISION_PACKAGE_VERSION

    def __post_init__(self) -> None:
        if self.version != DECISION_PACKAGE_VERSION:
            raise DecisionPackageContractError("result version must bind DecisionPackage-2.0")
        if len(self.packages) > MAX_PACKAGES_PER_RESULT:
            raise DecisionPackageContractError("result package count exceeds the bound")
        if any(not isinstance(package, DecisionPackage) for package in self.packages):
            raise DecisionPackageContractError("result packages must be contract packages")
        packages = _canonical_tuple(
            self.packages,
            key=lambda item: item.package_id,
            label="result packages",
        )
        if any(
            package.policy != self.policy or package.version_context != self.version_context
            for package in packages
        ):
            raise DecisionPackageContractError(
                "result packages must share policy and version context"
            )
        object.__setattr__(self, "packages", packages)

    @property
    def fingerprint(self) -> str:
        return sha256_fingerprint(
            {
                "version": self.version,
                "kind": "decision_package_result",
                "package_ids": tuple(package.package_id for package in self.packages),
                "policy_fingerprint": self.policy.fingerprint,
                "version_context_fingerprint": self.version_context.fingerprint,
            }
        )

    @property
    def result_id(self) -> str:
        return _opaque_id("decision-package-result", self.fingerprint)
