"""Deterministic, complete-linkage clustering for DecisionPackage-2.0 atoms.

This module consumes only the inert decision-package DTOs.  It deliberately
does not inspect source terms, vectors, or ranking scores: a family is a safe
candidate only when every one of its pairs is explicitly compatible.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import combinations

from .decision_packages_v2 import (
    MAX_ATOMS_PER_FAMILY,
    MAX_PACKAGES_PER_RESULT,
    MAX_PAIR_CONSTRAINTS_PER_PACKAGE,
    BlockerCode,
    CandidateFamily,
    PackageAtom,
    PairConstraint,
    PairRelation,
    UnitCompatibility,
)

CLUSTERING_VERSION = "ConstrainedClustering-1.0"
MAX_CLUSTERING_ATOMS = MAX_PACKAGES_PER_RESULT


class ClusteringContractError(ValueError):
    """Controlled clustering input or output invariant failure."""


@dataclass(frozen=True, slots=True)
class ClusteringResult:
    """Disjoint safe candidates plus explicit manual and outlier paths.

    ``candidate_families`` are ready for the bounded package optimizer.  An
    atom appears in exactly one of the three result paths, while constraints
    are retained separately so a caller can keep the complete audit context.
    """

    candidate_families: tuple[CandidateFamily, ...]
    manual_families: tuple[CandidateFamily, ...] = ()
    outlier_atoms: tuple[PackageAtom, ...] = ()
    pair_constraints: tuple[PairConstraint, ...] = ()
    version: str = CLUSTERING_VERSION

    def __post_init__(self) -> None:
        if self.version != CLUSTERING_VERSION:
            raise ClusteringContractError("clustering result version is unsupported")
        if len(self.candidate_families) + len(self.manual_families) > MAX_PACKAGES_PER_RESULT:
            raise ClusteringContractError("clustering family count is out of bounds")
        if any(not isinstance(family, CandidateFamily) for family in self.candidate_families):
            raise ClusteringContractError("candidate families must be contract families")
        if any(not isinstance(family, CandidateFamily) for family in self.manual_families):
            raise ClusteringContractError("manual families must be contract families")
        candidates = _canonical_families(self.candidate_families, "candidate families")
        manuals = _canonical_families(self.manual_families, "manual families")
        if any(not _is_safe_candidate(family) for family in candidates):
            raise ClusteringContractError("candidate family is not complete-linkage safe")
        if any(not family.is_manual_family for family in manuals):
            raise ClusteringContractError("manual family requires a controlled blocker")
        if any(not isinstance(atom, PackageAtom) for atom in self.outlier_atoms):
            raise ClusteringContractError("outlier atoms must be contract atoms")
        outliers = tuple(sorted(self.outlier_atoms, key=lambda atom: atom.atom_id))
        if len(outliers) != len({atom.atom_id for atom in outliers}):
            raise ClusteringContractError("outlier atoms must be unique")
        if len(self.pair_constraints) > MAX_PAIR_CONSTRAINTS_PER_PACKAGE:
            raise ClusteringContractError("clustering pair constraints exceed the bound")
        if any(not isinstance(constraint, PairConstraint) for constraint in self.pair_constraints):
            raise ClusteringContractError("clustering constraints must be controlled")
        constraints = tuple(sorted(self.pair_constraints, key=lambda item: item.pair_key))
        if len(constraints) != len({constraint.pair_key for constraint in constraints}):
            raise ClusteringContractError("clustering constraints must be unique")

        member_atoms = (
            tuple(atom for family in (*candidates, *manuals) for atom in family.atoms) + outliers
        )
        member_ids = {atom.atom_id for atom in member_atoms}
        if len(member_atoms) != len(member_ids):
            raise ClusteringContractError("clustering atom membership must be unique")
        if len(member_atoms) != len({atom.semantic_ref for atom in member_atoms}):
            raise ClusteringContractError("clustering semantic membership must be unique")
        if any(not set(constraint.pair_key) <= member_ids for constraint in constraints):
            raise ClusteringContractError("clustering constraints must reference result atoms")

        object.__setattr__(self, "candidate_families", candidates)
        object.__setattr__(self, "manual_families", manuals)
        object.__setattr__(self, "outlier_atoms", outliers)
        object.__setattr__(self, "pair_constraints", constraints)

    @property
    def families(self) -> tuple[CandidateFamily, ...]:
        """Compatibility alias for the safe, optimizer-ready candidates."""
        return self.candidate_families

    @property
    def outlier_atom_ids(self) -> tuple[str, ...]:
        return tuple(atom.atom_id for atom in self.outlier_atoms)

    @property
    def outlier_semantic_refs(self) -> tuple[str, ...]:
        return tuple(atom.semantic_ref for atom in self.outlier_atoms)


def cluster_atoms(
    atoms: Iterable[PackageAtom], pair_constraints: Iterable[PairConstraint]
) -> ClusteringResult:
    """Build deterministic category-aware complete-linkage candidates.

    Exact boundaries are a hard partition.  Within an eligible boundary,
    critical and typed signatures are hard subpartitions.  A merge happens
    only after every cross pair is present and ``PairConstraint.is_compatible``
    is true; this intentionally prevents transitive/union-find closure.
    """
    ordered_atoms = _normalize_atoms(atoms)
    constraints = _normalize_constraints(pair_constraints, ordered_atoms)
    constraints_by_pair = {constraint.pair_key: constraint for constraint in constraints}

    candidates: list[CandidateFamily] = []
    manuals: list[CandidateFamily] = []
    outliers: list[PackageAtom] = []
    by_boundary: dict[object, list[PackageAtom]] = defaultdict(list)
    for atom in ordered_atoms:
        by_boundary[atom.boundary].append(atom)

    for boundary in sorted(by_boundary, key=lambda item: item.fingerprint):
        boundary_atoms = tuple(sorted(by_boundary[boundary], key=lambda atom: atom.atom_id))
        boundary_constraints = _constraints_for_atoms(boundary_atoms, constraints_by_pair)
        if not _boundary_can_be_safe(boundary):
            manuals.extend(
                _manual_families(
                    boundary_atoms,
                    boundary_constraints,
                    _boundary_blocker(boundary),
                )
            )
            continue

        by_critical: dict[str, list[PackageAtom]] = defaultdict(list)
        for atom in boundary_atoms:
            by_critical[atom.critical_signature_ref].append(atom)
        for critical_ref in sorted(by_critical):
            by_typed: dict[str, list[PackageAtom]] = defaultdict(list)
            for atom in by_critical[critical_ref]:
                by_typed[atom.typed_signature_ref].append(atom)
            for typed_ref in sorted(by_typed):
                cohort = tuple(sorted(by_typed[typed_ref], key=lambda atom: atom.atom_id))
                cohort_constraints = _constraints_for_atoms(cohort, constraints_by_pair)
                if any(atom.manual_blockers for atom in cohort):
                    manuals.extend(
                        _manual_families(cohort, cohort_constraints, BlockerCode.MANUAL_REVIEW)
                    )
                    continue
                cohort_candidates, cohort_manuals, cohort_outliers = _cluster_cohort(
                    cohort, constraints_by_pair
                )
                candidates.extend(cohort_candidates)
                manuals.extend(cohort_manuals)
                outliers.extend(cohort_outliers)

    return ClusteringResult(
        candidate_families=tuple(candidates),
        manual_families=tuple(manuals),
        outlier_atoms=tuple(outliers),
        pair_constraints=constraints,
    )


def _normalize_atoms(atoms: Iterable[PackageAtom]) -> tuple[PackageAtom, ...]:
    try:
        values = tuple(atoms)
    except TypeError as error:
        raise ClusteringContractError("clustering atoms must be iterable") from error
    if not values or len(values) > MAX_CLUSTERING_ATOMS:
        raise ClusteringContractError("clustering atom count is out of bounds")
    if any(not isinstance(atom, PackageAtom) for atom in values):
        raise ClusteringContractError("clustering atoms must be contract atoms")
    ordered = tuple(sorted(values, key=lambda atom: atom.atom_id))
    if len(ordered) != len({atom.atom_id for atom in ordered}):
        raise ClusteringContractError("clustering atoms must be unique")
    if len(ordered) != len({atom.semantic_ref for atom in ordered}):
        raise ClusteringContractError("clustering semantic atoms must be unique")
    return ordered


def _normalize_constraints(
    pair_constraints: Iterable[PairConstraint], atoms: tuple[PackageAtom, ...]
) -> tuple[PairConstraint, ...]:
    try:
        values = tuple(pair_constraints)
    except TypeError as error:
        raise ClusteringContractError("clustering constraints must be iterable") from error
    if len(values) > MAX_PAIR_CONSTRAINTS_PER_PACKAGE:
        raise ClusteringContractError("clustering pair constraints exceed the bound")
    if any(not isinstance(constraint, PairConstraint) for constraint in values):
        raise ClusteringContractError("clustering constraints must be controlled")
    ordered = tuple(sorted(values, key=lambda constraint: constraint.pair_key))
    if len(ordered) != len({constraint.pair_key for constraint in ordered}):
        raise ClusteringContractError("clustering constraints must be unique")
    atom_ids = {atom.atom_id for atom in atoms}
    if any(not set(constraint.pair_key) <= atom_ids for constraint in ordered):
        raise ClusteringContractError("clustering constraints must reference input atoms")
    return ordered


def _boundary_can_be_safe(boundary: object) -> bool:
    return bool(
        getattr(boundary, "is_known", False)
        and getattr(boundary, "unit_compatibility", None) is UnitCompatibility.COMPATIBLE
    )


def _boundary_blocker(boundary: object) -> BlockerCode:
    if not getattr(boundary, "is_known", False):
        return BlockerCode.MANUAL_REVIEW
    return BlockerCode.PATTERN_UNATTESTED


def _cluster_cohort(
    cohort: tuple[PackageAtom, ...], constraints_by_pair: dict[tuple[str, str], PairConstraint]
) -> tuple[list[CandidateFamily], list[CandidateFamily], list[PackageAtom]]:
    if len(cohort) == 1:
        return [CandidateFamily(cohort)], [], []

    clusters: list[tuple[PackageAtom, ...]] = [(atom,) for atom in cohort]
    while True:
        mergeable: list[tuple[tuple[str, ...], int, int]] = []
        for left_index, right_index in combinations(range(len(clusters)), 2):
            left, right = clusters[left_index], clusters[right_index]
            merged = tuple(sorted((*left, *right), key=lambda atom: atom.atom_id))
            if len(merged) <= MAX_ATOMS_PER_FAMILY and _can_complete_link(
                left, right, constraints_by_pair
            ):
                mergeable.append((tuple(atom.atom_id for atom in merged), left_index, right_index))
        if not mergeable:
            break
        _, left_index, right_index = min(mergeable)
        merged = tuple(
            sorted((*clusters[left_index], *clusters[right_index]), key=lambda atom: atom.atom_id)
        )
        clusters = [
            cluster
            for index, cluster in enumerate(clusters)
            if index not in (left_index, right_index)
        ]
        clusters.append(merged)
        clusters.sort(key=lambda cluster: tuple(atom.atom_id for atom in cluster))

    safe_clusters = [cluster for cluster in clusters if len(cluster) > 1]
    singletons = [cluster[0] for cluster in clusters if len(cluster) == 1]
    if not safe_clusters:
        constraints = _constraints_for_atoms(cohort, constraints_by_pair)
        return [], _manual_families(cohort, constraints, _constraint_blocker(constraints)), []

    candidates = [
        CandidateFamily(cluster, _constraints_for_atoms(cluster, constraints_by_pair))
        for cluster in safe_clusters
    ]
    return candidates, [], singletons


def _can_complete_link(
    left: tuple[PackageAtom, ...],
    right: tuple[PackageAtom, ...],
    constraints_by_pair: dict[tuple[str, str], PairConstraint],
) -> bool:
    return all(
        (
            constraint := constraints_by_pair.get(
                tuple(sorted((left_atom.atom_id, right_atom.atom_id)))
            )
        )
        is not None
        and constraint.is_compatible
        for left_atom in left
        for right_atom in right
    )


def _constraints_for_atoms(
    atoms: tuple[PackageAtom, ...], constraints_by_pair: dict[tuple[str, str], PairConstraint]
) -> tuple[PairConstraint, ...]:
    return tuple(
        constraint
        for pair in combinations(tuple(atom.atom_id for atom in atoms), 2)
        if (constraint := constraints_by_pair.get(pair)) is not None
    )


def _manual_families(
    atoms: tuple[PackageAtom, ...],
    constraints: tuple[PairConstraint, ...],
    blocker: BlockerCode,
) -> list[CandidateFamily]:
    families: list[CandidateFamily] = []
    for start in range(0, len(atoms), MAX_ATOMS_PER_FAMILY):
        members = atoms[start : start + MAX_ATOMS_PER_FAMILY]
        member_ids = {atom.atom_id for atom in members}
        family_constraints = tuple(
            constraint for constraint in constraints if set(constraint.pair_key) <= member_ids
        )
        families.append(CandidateFamily(members, family_constraints, blocker_codes=(blocker,)))
    return families


def _constraint_blocker(constraints: tuple[PairConstraint, ...]) -> BlockerCode:
    if any(constraint.relation is PairRelation.CANNOT_LINK for constraint in constraints):
        return BlockerCode.CANNOT_LINK
    if any(constraint.relation is PairRelation.MANUAL_REVIEW for constraint in constraints):
        return BlockerCode.MANUAL_REVIEW
    return BlockerCode.PATTERN_UNATTESTED


def _is_safe_candidate(family: CandidateFamily) -> bool:
    boundary = family.boundary
    return bool(
        boundary is not None
        and _boundary_can_be_safe(boundary)
        and not family.is_manual_family
        and family.has_complete_pair_coverage
        and family.all_pairs_compatible
        and len({atom.critical_signature_ref for atom in family.atoms}) == 1
        and len({atom.typed_signature_ref for atom in family.atoms}) == 1
    )


def _canonical_families(
    families: tuple[CandidateFamily, ...], label: str
) -> tuple[CandidateFamily, ...]:
    ordered = tuple(sorted(families, key=lambda family: family.family_id))
    if len(ordered) != len({family.family_id for family in ordered}):
        raise ClusteringContractError(f"{label} must be unique")
    return ordered
