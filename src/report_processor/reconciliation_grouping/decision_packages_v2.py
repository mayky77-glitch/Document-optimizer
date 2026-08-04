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

from report_processor.reconciliation_patterns.hybrid_retrieval import (
    AuthorityEnvelope,
    HybridQuery,
    HybridRetrievalResult,
    HybridStatus,
)
from report_processor.reconciliation_patterns.pattern_registry import DecisionSource

DECISION_PACKAGE_VERSION = "DecisionPackage-2.0"
MAX_ATOMS_PER_FAMILY = 128
MAX_FAMILIES_PER_PACKAGE = 64
MAX_PACKAGES_PER_RESULT = 512
MAX_PAIR_CONSTRAINTS_PER_PACKAGE = 8_192

_SHA_REF = re.compile(r"sha256:[0-9a-f]{64}\Z")
_VERSION = re.compile(r"[A-Za-z][A-Za-z0-9_-]*-\d+\.\d+\Z")
_ATOM_ID = re.compile(r"package-atom-[0-9a-f]{64}\Z")


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


class BlockerCode(StrEnum):
    """Closed, privacy-safe reasons that keep a path visible but non-safe."""

    AUTHORITY_UNATTESTED = "authority_unattested"
    CANNOT_LINK = "cannot_link"
    MANUAL_REVIEW = "manual_review"
    OUTLIER = "outlier"
    PATTERN_UNATTESTED = "pattern_unattested"


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


def _require_atom_id(value: str, *, field_name: str) -> None:
    if not isinstance(value, str) or not _ATOM_ID.fullmatch(value):
        raise DecisionPackageContractError(f"{field_name} must be a canonical package atom ID")


def _canonical_tuple(values: tuple[Any, ...], *, key: Any, label: str) -> tuple[Any, ...]:
    if len(values) != len({key(value) for value in values}):
        raise DecisionPackageContractError(f"{label} must be unique")
    return tuple(sorted(values, key=key))


def _canonical_refs(values: tuple[str, ...], *, label: str) -> tuple[str, ...]:
    if any(not isinstance(value, str) for value in values):
        raise DecisionPackageContractError(f"{label} must contain opaque references")
    for value in values:
        _require_sha_ref(value, field_name=label)
    return _canonical_tuple(values, key=lambda value: value, label=label)


def _canonical_blockers(values: tuple[BlockerCode, ...], *, label: str) -> tuple[BlockerCode, ...]:
    if any(not isinstance(value, BlockerCode) for value in values):
        raise DecisionPackageContractError(f"{label} must contain controlled blocker codes")
    return _canonical_tuple(values, key=lambda value: value.value, label=label)


def _require_unique_semantic_refs(atoms: tuple[PackageAtom, ...], *, label: str) -> None:
    if len(atoms) != len({atom.semantic_ref for atom in atoms}):
        raise DecisionPackageContractError(f"{label} must not repeat semantic references")


@dataclass(frozen=True, slots=True)
class PackageBoundary:
    """Controlled outcome boundary for atoms, families, and packages."""

    category_ref: str | None
    mode: PackageMode | None
    unit_compatibility: UnitCompatibility
    unit_ref: str
    action_ref: str | None
    object_ref: str | None

    def __post_init__(self) -> None:
        if self.mode is not None and not isinstance(self.mode, PackageMode):
            raise DecisionPackageContractError("mode must be controlled")
        if not isinstance(self.unit_compatibility, UnitCompatibility):
            raise DecisionPackageContractError("unit compatibility must be controlled")
        _require_sha_ref(self.unit_ref, field_name="unit_ref")
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
    atom_version_ref: str
    critical_signature_ref: str
    typed_signature_ref: str
    outcome_ref: str
    boundary: PackageBoundary
    manual_blockers: tuple[BlockerCode, ...] = ()
    version: str = DECISION_PACKAGE_VERSION

    def __post_init__(self) -> None:
        _require_sha_ref(self.semantic_ref, field_name="semantic_ref")
        _require_sha_ref(self.atom_version_ref, field_name="atom_version_ref")
        _require_sha_ref(self.critical_signature_ref, field_name="critical_signature_ref")
        _require_sha_ref(self.typed_signature_ref, field_name="typed_signature_ref")
        _require_sha_ref(self.outcome_ref, field_name="outcome_ref")
        if not isinstance(self.boundary, PackageBoundary):
            raise DecisionPackageContractError("atom boundary must be controlled")
        if self.version != DECISION_PACKAGE_VERSION:
            raise DecisionPackageContractError("atom version must bind DecisionPackage-2.0")
        object.__setattr__(
            self,
            "manual_blockers",
            _canonical_blockers(self.manual_blockers, label="atom manual blockers"),
        )

    @property
    def fingerprint(self) -> str:
        return sha256_fingerprint(
            {
                "version": self.version,
                "kind": "atom",
                "semantic_ref": self.semantic_ref,
                "atom_version_ref": self.atom_version_ref,
                "critical_signature_ref": self.critical_signature_ref,
                "typed_signature_ref": self.typed_signature_ref,
                "outcome_ref": self.outcome_ref,
                "boundary": self.boundary,
                "manual_blockers": self.manual_blockers,
            }
        )

    @property
    def atom_id(self) -> str:
        return _opaque_id("package-atom", self.fingerprint)


@dataclass(frozen=True, slots=True, init=False)
class AuthoritativePairAttestation:
    """Sealed pair evidence derived only from a validated Wave 6 authority."""

    left_query_fingerprint: str
    right_query_fingerprint: str
    left_authority_fingerprint: str
    right_authority_fingerprint: str
    outcome_fingerprint: str
    scope_ref: str
    consequential_context_ref: str
    left_atom_id: str
    right_atom_id: str
    attestation_ref: str
    version: str = DECISION_PACKAGE_VERSION

    def __init__(self, *_: object, **__: object) -> None:
        raise DecisionPackageContractError("attestations are sealed")

    @classmethod
    def from_authoritative_results(
        cls,
        left_atom: PackageAtom,
        left_query: HybridQuery,
        left_result: HybridRetrievalResult,
        right_atom: PackageAtom,
        right_query: HybridQuery,
        right_result: HybridRetrievalResult,
        version_context: DecisionPackageVersionContext,
    ) -> AuthoritativePairAttestation:
        if not isinstance(version_context, DecisionPackageVersionContext):
            raise DecisionPackageContractError("controlled version context is required")
        left_authority = _validated_authority(left_atom, left_query, left_result)
        right_authority = _validated_authority(right_atom, right_query, right_result)
        chains = tuple(
            sorted(
                (
                    (left_atom, left_query, left_authority),
                    (right_atom, right_query, right_authority),
                ),
                key=lambda chain: chain[0].atom_id,
            )
        )
        (left_atom, left_query, left_authority), (right_atom, right_query, right_authority) = chains
        if (
            left_authority.decision.outcome != right_authority.decision.outcome
            or tuple(
                getattr(left_query, name)
                for name in (
                    "tenant_ref",
                    "project_ref",
                    "document_type_fingerprint",
                    "taxonomy_version_fingerprint",
                    "scope_fingerprint",
                    "consequential_version_fingerprint",
                )
            )
            != tuple(
                getattr(right_query, name)
                for name in (
                    "tenant_ref",
                    "project_ref",
                    "document_type_fingerprint",
                    "taxonomy_version_fingerprint",
                    "scope_fingerprint",
                    "consequential_version_fingerprint",
                )
            )
            or left_query.consequential_version_fingerprint != version_context.authority_context_ref
            or left_authority.decision.outcome.mode != left_atom.boundary.mode.value
            or right_authority.decision.outcome.mode != right_atom.boundary.mode.value
            or left_atom.outcome_ref != sha256_fingerprint(left_authority.decision.outcome)
            or right_atom.outcome_ref != sha256_fingerprint(right_authority.decision.outcome)
            or left_atom.boundary.category_ref
            != sha256_fingerprint(left_authority.decision.outcome.target_category)
            or right_atom.boundary.category_ref
            != sha256_fingerprint(right_authority.decision.outcome.target_category)
        ):
            raise DecisionPackageContractError("supported authoritative evidence is required")
        if left_atom.atom_id == right_atom.atom_id:
            raise DecisionPackageContractError("attestations cannot be self-referential")
        left, right = sorted((left_atom.atom_id, right_atom.atom_id))
        outcome_fingerprint = sha256_fingerprint(left_authority.decision.outcome)
        attestation_ref = sha256_fingerprint(
            {
                "version": DECISION_PACKAGE_VERSION,
                "kind": "authoritative_pair_attestation",
                "left_query_fingerprint": left_query.fingerprint,
                "right_query_fingerprint": right_query.fingerprint,
                "left_authority_fingerprint": left_authority.fingerprint,
                "right_authority_fingerprint": right_authority.fingerprint,
                "outcome_fingerprint": outcome_fingerprint,
                "scope_ref": left_query.scope_fingerprint,
                "consequential_context_ref": left_query.consequential_version_fingerprint,
                "left_atom_id": left,
                "right_atom_id": right,
            }
        )
        attestation = object.__new__(cls)
        for name, value in {
            "left_query_fingerprint": left_query.fingerprint,
            "right_query_fingerprint": right_query.fingerprint,
            "left_authority_fingerprint": left_authority.fingerprint,
            "right_authority_fingerprint": right_authority.fingerprint,
            "outcome_fingerprint": outcome_fingerprint,
            "scope_ref": left_query.scope_fingerprint,
            "consequential_context_ref": left_query.consequential_version_fingerprint,
            "left_atom_id": left,
            "right_atom_id": right,
            "attestation_ref": attestation_ref,
            "version": DECISION_PACKAGE_VERSION,
        }.items():
            object.__setattr__(attestation, name, value)
        return attestation

    @property
    def pair_key(self) -> tuple[str, str]:
        return (self.left_atom_id, self.right_atom_id)


def _validated_authority(
    atom: PackageAtom, query: HybridQuery, result: HybridRetrievalResult
) -> AuthorityEnvelope:
    if (
        not isinstance(atom, PackageAtom)
        or not isinstance(query, HybridQuery)
        or not isinstance(result, HybridRetrievalResult)
        or atom.semantic_ref != query.query_ref
        or result.query_fingerprint != query.fingerprint
        or result.status
        not in (HybridStatus.AUTHORITATIVE_EXACT, HybridStatus.AUTHORITATIVE_PATTERN)
        or not isinstance(result.authority, AuthorityEnvelope)
        or result.authority.query_fingerprint != query.fingerprint
        or result.authority.decision.source
        not in (DecisionSource.EXACT_FEEDBACK, DecisionSource.ACTIVE_PATTERN)
    ):
        raise DecisionPackageContractError("supported authoritative evidence is required")
    return result.authority


@dataclass(frozen=True, slots=True)
class PairConstraint:
    """Canonical complete-linkage relation for one pair of opaque atoms."""

    left_atom_id: str
    right_atom_id: str
    relation: PairRelation
    attestation: AuthoritativePairAttestation | None = None
    blocker_codes: tuple[BlockerCode, ...] = ()
    version: str = DECISION_PACKAGE_VERSION

    def __post_init__(self) -> None:
        if self.version != DECISION_PACKAGE_VERSION:
            raise DecisionPackageContractError(
                "pair constraint version must bind DecisionPackage-2.0"
            )
        _require_atom_id(self.left_atom_id, field_name="left_atom_id")
        _require_atom_id(self.right_atom_id, field_name="right_atom_id")
        if self.left_atom_id == self.right_atom_id:
            raise DecisionPackageContractError("pair constraints cannot be self-referential")
        if not isinstance(self.relation, PairRelation):
            raise DecisionPackageContractError("pair relation must be controlled")
        left, right = sorted((self.left_atom_id, self.right_atom_id))
        object.__setattr__(self, "left_atom_id", left)
        object.__setattr__(self, "right_atom_id", right)
        if self.attestation is not None:
            if self.relation is not PairRelation.MUST_LINK:
                raise DecisionPackageContractError(
                    "only must-link constraints may carry attestations"
                )
            if not isinstance(self.attestation, AuthoritativePairAttestation):
                raise DecisionPackageContractError("pair attestation must be controlled")
            if self.attestation.pair_key != (left, right):
                raise DecisionPackageContractError(
                    "attestation must bind the constrained atom pair"
                )
        object.__setattr__(
            self,
            "blocker_codes",
            _canonical_blockers(self.blocker_codes, label="pair blocker codes"),
        )

    @property
    def pair_key(self) -> tuple[str, str]:
        return (self.left_atom_id, self.right_atom_id)

    @property
    def is_compatible(self) -> bool:
        return (
            self.relation is PairRelation.MUST_LINK
            and self.attestation is not None
            and not self.blocker_codes
        )

    def is_compatible_in_context(self, context_ref: str) -> bool:
        """Return true only for an authoritative attestation of this exact context."""
        return bool(
            self.is_compatible
            and self.attestation is not None
            and self.attestation.consequential_context_ref == context_ref
        )

    @property
    def fingerprint(self) -> str:
        return sha256_fingerprint(
            {
                "version": self.version,
                "kind": "pair_constraint",
                "left_atom_id": self.left_atom_id,
                "right_atom_id": self.right_atom_id,
                "relation": self.relation,
                "attestation_ref": self.attestation.attestation_ref if self.attestation else None,
                "blocker_codes": self.blocker_codes,
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
    blocker_codes: tuple[BlockerCode, ...] = ()
    outlier_atom_ids: tuple[str, ...] = ()
    version: str = DECISION_PACKAGE_VERSION

    def __post_init__(self) -> None:
        if self.version != DECISION_PACKAGE_VERSION:
            raise DecisionPackageContractError(
                "candidate family version must bind DecisionPackage-2.0"
            )
        if not self.atoms or len(self.atoms) > MAX_ATOMS_PER_FAMILY:
            raise DecisionPackageContractError("candidate family atom count is out of bounds")
        if any(not isinstance(atom, PackageAtom) for atom in self.atoms):
            raise DecisionPackageContractError("candidate atoms must be contract atoms")
        atoms = _canonical_tuple(self.atoms, key=lambda item: item.atom_id, label="candidate atoms")
        _require_unique_semantic_refs(atoms, label="candidate atoms")
        if len({atom.critical_signature_ref for atom in atoms}) != 1:
            raise DecisionPackageContractError("candidate atoms must share a critical signature")
        if len({atom.typed_signature_ref for atom in atoms}) != 1:
            raise DecisionPackageContractError("candidate atoms must share a typed signature")
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
        object.__setattr__(
            self,
            "blocker_codes",
            _canonical_blockers(self.blocker_codes, label="candidate blocker codes"),
        )
        outlier_atom_ids = _canonical_tuple(
            self.outlier_atom_ids,
            key=lambda value: value,
            label="candidate outlier atom IDs",
        )
        for value in outlier_atom_ids:
            _require_atom_id(value, field_name="candidate outlier atom ID")
        if set(outlier_atom_ids).intersection(atom_ids):
            raise DecisionPackageContractError("candidate outliers cannot also be family members")
        object.__setattr__(self, "outlier_atom_ids", outlier_atom_ids)

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
    def is_manual_family(self) -> bool:
        return bool(self.blocker_codes) or any(atom.manual_blockers for atom in self.atoms)

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
                "blocker_codes": self.blocker_codes,
                "outlier_atom_ids": self.outlier_atom_ids,
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

    @property
    def identity_fingerprint(self) -> str:
        return sha256_fingerprint(
            {
                "kind": "optimizer_policy_identity",
                "policy_ref": self.policy_ref,
                "max_safe_atoms": self.max_safe_atoms,
                "max_families": self.max_families,
                "max_pair_constraints": self.max_pair_constraints,
            }
        )


@dataclass(frozen=True, slots=True)
class DecisionPackageVersionContext:
    """Consequential, controlled versions required to interpret a package."""

    semantic_contract_version: str
    feedback_contract_version: str
    clustering_contract_version: str
    optimizer_policy_version: str
    authority_context_ref: str
    consequential_refs: tuple[str, ...]
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
        _require_sha_ref(self.authority_context_ref, field_name="authority_context_ref")
        if not self.consequential_refs:
            raise DecisionPackageContractError("context consequential refs must be non-empty")
        object.__setattr__(
            self,
            "consequential_refs",
            _canonical_refs(self.consequential_refs, label="context consequential refs"),
        )

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
        _require_unique_semantic_refs(atoms, label="package atoms")
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
            and bool(boundary.unit_ref)
            and len(self.atoms) <= self.policy.max_safe_atoms
            and not any(family.is_manual_family for family in self.families)
            and not any(atom.manual_blockers for atom in self.atoms)
            and len({atom.critical_signature_ref for atom in self.atoms}) == 1
            and len({atom.typed_signature_ref for atom in self.atoms}) == 1
            and all(family.all_pairs_compatible for family in self.families)
            and self.has_complete_pair_coverage
            and all(
                constraint.is_compatible_in_context(self.version_context.authority_context_ref)
                for constraint in self.pair_constraints
            )
        )

    @property
    def fingerprint(self) -> str:
        return sha256_fingerprint(
            {
                "version": self.version,
                "kind": "decision_package_revision",
                "identity_fingerprint": self.identity_fingerprint,
                "policy_fingerprint": self.policy.fingerprint,
                "version_context_fingerprint": self.version_context.fingerprint,
            }
        )

    @property
    def identity_fingerprint(self) -> str:
        return sha256_fingerprint(
            {
                "version": self.version,
                "kind": "decision_package_identity",
                "family_ids": tuple(family.family_id for family in self.families),
                "pair_constraint_ids": tuple(
                    constraint.constraint_id for constraint in self.pair_constraints
                ),
                "policy_identity_fingerprint": self.policy.identity_fingerprint,
            }
        )

    @property
    def package_id(self) -> str:
        return _opaque_id("decision-package", self.identity_fingerprint)

    @property
    def action_reduction(self) -> int:
        return max(0, len(self.atoms) - 1)


@dataclass(frozen=True, slots=True)
class DecisionPackageResult:
    """The inert, ordered package output for one exact policy and context."""

    packages: tuple[DecisionPackage, ...]
    policy: OptimizerPolicy
    version_context: DecisionPackageVersionContext
    manual_families: tuple[CandidateFamily, ...] = ()
    outlier_atoms: tuple[PackageAtom, ...] = ()
    blocker_codes: tuple[BlockerCode, ...] = ()
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
        if any(not isinstance(family, CandidateFamily) for family in self.manual_families):
            raise DecisionPackageContractError("manual families must be contract families")
        manual_families = _canonical_tuple(
            self.manual_families,
            key=lambda family: family.family_id,
            label="manual families",
        )
        if any(not family.is_manual_family for family in manual_families):
            raise DecisionPackageContractError("manual family paths require controlled blockers")
        object.__setattr__(self, "manual_families", manual_families)
        if any(not isinstance(atom, PackageAtom) for atom in self.outlier_atoms):
            raise DecisionPackageContractError("outlier atoms must be contract atoms")
        outlier_atoms = _canonical_tuple(
            self.outlier_atoms,
            key=lambda atom: atom.atom_id,
            label="outlier atoms",
        )
        object.__setattr__(self, "outlier_atoms", outlier_atoms)
        object.__setattr__(
            self,
            "blocker_codes",
            _canonical_blockers(self.blocker_codes, label="result blocker codes"),
        )
        package_families = tuple(family for package in packages for family in package.families)
        package_family_ids = {family.family_id for family in package_families}
        if package_family_ids.intersection(family.family_id for family in manual_families):
            raise DecisionPackageContractError("manual families cannot also be package families")
        package_atom_ids = {atom.atom_id for package in packages for atom in package.atoms}
        manual_atom_ids = {atom.atom_id for family in manual_families for atom in family.atoms}
        outlier_atom_ids = {atom.atom_id for atom in outlier_atoms}
        total_membership_count = (
            sum(len(package.atoms) for package in packages)
            + sum(len(family.atoms) for family in manual_families)
            + len(outlier_atoms)
        )
        if (
            package_atom_ids.intersection(manual_atom_ids)
            or package_atom_ids.intersection(outlier_atom_ids)
            or manual_atom_ids.intersection(outlier_atom_ids)
            or len(package_atom_ids | manual_atom_ids | outlier_atom_ids) != total_membership_count
        ):
            raise DecisionPackageContractError("result atom membership must be unique")
        declared_outlier_ids = {
            atom_id
            for family in (*package_families, *manual_families)
            for atom_id in family.outlier_atom_ids
        }
        if declared_outlier_ids != outlier_atom_ids:
            raise DecisionPackageContractError("visible outliers must match family outlier paths")
        all_atoms = (
            tuple(atom for package in packages for atom in package.atoms)
            + tuple(atom for family in manual_families for atom in family.atoms)
            + outlier_atoms
        )
        _require_unique_semantic_refs(all_atoms, label="result atoms")

    @property
    def manual_family_ids(self) -> tuple[str, ...]:
        return tuple(family.family_id for family in self.manual_families)

    @property
    def outlier_atom_ids(self) -> tuple[str, ...]:
        return tuple(atom.atom_id for atom in self.outlier_atoms)

    @property
    def action_reduction(self) -> int:
        return sum(package.action_reduction for package in self.packages if package.safe)

    @property
    def fingerprint(self) -> str:
        return sha256_fingerprint(
            {
                "version": self.version,
                "kind": "decision_package_result_revision",
                "identity_fingerprint": self.identity_fingerprint,
                "package_ids": tuple(package.package_id for package in self.packages),
                "policy_fingerprint": self.policy.fingerprint,
                "version_context_fingerprint": self.version_context.fingerprint,
                "manual_family_ids": self.manual_family_ids,
                "outlier_atom_ids": self.outlier_atom_ids,
                "blocker_codes": self.blocker_codes,
            }
        )

    @property
    def identity_fingerprint(self) -> str:
        return sha256_fingerprint(
            {
                "version": self.version,
                "kind": "decision_package_result_identity",
                "package_ids": tuple(package.package_id for package in self.packages),
                "policy_identity_fingerprint": self.policy.identity_fingerprint,
                "manual_family_ids": self.manual_family_ids,
                "outlier_atom_ids": self.outlier_atom_ids,
            }
        )

    @property
    def result_id(self) -> str:
        return _opaque_id("decision-package-result", self.identity_fingerprint)
