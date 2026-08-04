"""Exact, bounded package selection for constrained reconciliation families.

The optimizer only composes already attested DecisionPackage-2.0 objects.  It
does not inspect semantic text, vectors, scores, or hybrid availability.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from itertools import combinations

from .clustering import CLUSTERING_VERSION, ClusteringResult
from .decision_packages_v2 import (
    BlockerCode,
    CandidateFamily,
    DecisionPackage,
    DecisionPackageResult,
    DecisionPackageVersionContext,
    OptimizerPolicy,
    PackageAtom,
    PairConstraint,
    UnitCompatibility,
)

OPTIMIZER_VERSION = "DecisionPackageOptimizer-1.0"
"""Version of this deterministic selection procedure."""

MAX_SEARCH_STATES = 100_000
"""Finite proof budget; exhaustion fails closed instead of guessing an optimum."""


class OptimizerContractError(ValueError):
    """Controlled invalid optimizer input or unrepresentable result."""


class OptimizerSearchExhausted(OptimizerContractError):
    """The bounded exact search could not prove an optimum."""


def optimize_packages(
    clustering_result: ClusteringResult,
    policy: OptimizerPolicy,
    version_context: DecisionPackageVersionContext,
) -> DecisionPackageResult:
    """Return a proven-minimal, deterministic safe package partition.

    Candidate families remain indivisible except where a policy atom limit
    requires deterministic splitting.  Every emitted package is checked with
    all atom pairs, so a cross-family missing or cannot-link relation cannot
    turn into a safe package by transitive closure.
    """
    _validate_inputs(clustering_result, policy, version_context)
    constraints = {
        constraint.pair_key: constraint for constraint in clustering_result.pair_constraints
    }
    families = _split_oversized_families(clustering_result.candidate_families, policy)
    _validate_candidate_families(families, constraints)

    selected = _select_optimal_partition(families, constraints, policy)
    packages = tuple(
        _package_for_indices(indices, families, constraints, policy, version_context)
        for indices in selected
    )
    manual_families, package_families = _attach_outlier_paths(
        clustering_result.manual_families,
        packages,
        clustering_result.outlier_atoms,
    )
    packages = tuple(
        DecisionPackage(families, constraints, policy, version_context)
        for families, constraints in package_families
    )
    blockers = {blocker for family in manual_families for blocker in family.blocker_codes}
    if clustering_result.outlier_atoms:
        blockers.add(BlockerCode.OUTLIER)
    return DecisionPackageResult(
        packages,
        policy,
        version_context,
        manual_families=manual_families,
        outlier_atoms=clustering_result.outlier_atoms,
        blocker_codes=tuple(sorted(blockers, key=lambda item: item.value)),
    )


def _validate_inputs(
    clustering_result: ClusteringResult,
    policy: OptimizerPolicy,
    version_context: DecisionPackageVersionContext,
) -> None:
    if not isinstance(clustering_result, ClusteringResult):
        raise OptimizerContractError("clustering result must be controlled")
    if not isinstance(policy, OptimizerPolicy):
        raise OptimizerContractError("optimizer policy must be controlled")
    if not isinstance(version_context, DecisionPackageVersionContext):
        raise OptimizerContractError("version context must be controlled")
    if clustering_result.version != CLUSTERING_VERSION:
        raise OptimizerContractError("clustering result version is unsupported")
    if version_context.optimizer_policy_version != policy.version:
        raise OptimizerContractError("policy and version context must agree")
    declared_outliers = {
        atom_id
        for family in (*clustering_result.candidate_families, *clustering_result.manual_families)
        for atom_id in family.outlier_atom_ids
    }
    actual_outliers = {atom.atom_id for atom in clustering_result.outlier_atoms}
    if not declared_outliers <= actual_outliers:
        raise OptimizerContractError("family outliers must be visible result outliers")


def _split_oversized_families(
    families: tuple[CandidateFamily, ...], policy: OptimizerPolicy
) -> tuple[CandidateFamily, ...]:
    split: list[CandidateFamily] = []
    maximum_atoms = min(
        policy.max_safe_atoms, _max_atoms_for_pair_limit(policy.max_pair_constraints)
    )
    for family in sorted(families, key=lambda item: item.family_id):
        for start in range(0, len(family.atoms), maximum_atoms):
            atoms = family.atoms[start : start + maximum_atoms]
            atom_ids = {atom.atom_id for atom in atoms}
            split.append(
                CandidateFamily(
                    atoms,
                    tuple(
                        constraint
                        for constraint in family.pair_constraints
                        if set(constraint.pair_key) <= atom_ids
                    ),
                    blocker_codes=family.blocker_codes,
                )
            )
    return tuple(sorted(split, key=lambda item: item.family_id))


def _validate_candidate_families(
    families: tuple[CandidateFamily, ...], constraints: dict[tuple[str, str], PairConstraint]
) -> None:
    atom_ids: set[str] = set()
    semantic_refs: set[str] = set()
    for family in families:
        boundary = family.boundary
        if (
            family.is_manual_family
            or boundary is None
            or not boundary.is_known
            or boundary.unit_compatibility is not UnitCompatibility.COMPATIBLE
            or not family.has_complete_pair_coverage
            or not family.all_pairs_compatible
        ):
            raise OptimizerContractError("candidate family is not safe for optimizer selection")
        for atom in family.atoms:
            if atom.atom_id in atom_ids or atom.semantic_ref in semantic_refs:
                raise OptimizerContractError("candidate family membership must be unique")
            atom_ids.add(atom.atom_id)
            semantic_refs.add(atom.semantic_ref)
        for pair in combinations(family.atom_ids, 2):
            constraint = constraints.get(pair)
            if constraint is None or not constraint.is_compatible:
                raise OptimizerContractError("candidate family pairs must be explicitly compatible")


def _select_optimal_partition(
    families: tuple[CandidateFamily, ...],
    constraints: dict[tuple[str, str], PairConstraint],
    policy: OptimizerPolicy,
) -> tuple[tuple[int, ...], ...]:
    if not families:
        return ()
    atom_counts = tuple(len(family.atoms) for family in families)
    boundaries = tuple(family.boundary for family in families)
    compatible = tuple(
        tuple(
            _families_can_share(families[left], families[right], constraints)
            for right in range(len(families))
        )
        for left in range(len(families))
    )
    search_steps = 0
    memo: dict[int, tuple[tuple[int, ...], ...]] = {}

    def consume_search_step() -> None:
        nonlocal search_steps
        search_steps += 1
        if search_steps > MAX_SEARCH_STATES:
            raise OptimizerSearchExhausted("exact optimizer search bound exceeded")

    def solve(remaining: int) -> tuple[tuple[int, ...], ...]:
        if remaining == 0:
            return ()
        if remaining in memo:
            return memo[remaining]
        consume_search_step()
        first = (remaining & -remaining).bit_length() - 1
        available = [
            index
            for index in range(first + 1, len(families))
            if remaining & (1 << index)
            and boundaries[index] == boundaries[first]
            and compatible[first][index]
        ]
        choices = _package_choices(
            first, available, atom_counts, compatible, policy, consume_search_step
        )
        best: tuple[tuple[int, ...], ...] | None = None
        for choice in choices:
            choice_mask = sum(1 << index for index in choice)
            suffix = solve(remaining ^ choice_mask)
            candidate = _canonical_partition((choice, *suffix), families)
            if best is None or _partition_key(candidate, families) < _partition_key(best, families):
                best = candidate
        assert best is not None
        memo[remaining] = best
        return best

    return solve((1 << len(families)) - 1)


def _package_choices(
    first: int,
    available: list[int],
    atom_counts: tuple[int, ...],
    compatible: tuple[tuple[bool, ...], ...],
    policy: OptimizerPolicy,
    consume_search_step: Callable[[], None],
) -> tuple[tuple[int, ...], ...]:
    choices: list[tuple[int, ...]] = []

    def add_choices(selected: tuple[int, ...], candidates: list[int], atoms: int) -> None:
        consume_search_step()
        choices.append(selected)
        if len(selected) == policy.max_families:
            return
        for offset, candidate in enumerate(candidates):
            next_atoms = atoms + atom_counts[candidate]
            if (
                next_atoms > policy.max_safe_atoms
                or _pair_count(next_atoms) > policy.max_pair_constraints
            ):
                continue
            if all(compatible[candidate][existing] for existing in selected):
                add_choices((*selected, candidate), candidates[offset + 1 :], next_atoms)

    add_choices((first,), available, atom_counts[first])
    return tuple(
        sorted(
            choices,
            key=lambda choice: (-sum(atom_counts[index] for index in choice), -len(choice), choice),
        )
    )


def _families_can_share(
    left: CandidateFamily,
    right: CandidateFamily,
    constraints: dict[tuple[str, str], PairConstraint],
) -> bool:
    return all(
        (constraint := constraints.get(tuple(sorted((left_atom.atom_id, right_atom.atom_id)))))
        is not None
        and constraint.is_compatible
        for left_atom in left.atoms
        for right_atom in right.atoms
    )


def _max_atoms_for_pair_limit(limit: int) -> int:
    atoms = 1
    while _pair_count(atoms + 1) <= limit:
        atoms += 1
    return atoms


def _pair_count(atom_count: int) -> int:
    return atom_count * (atom_count - 1) // 2


def _canonical_partition(
    groups: tuple[tuple[int, ...], ...], families: tuple[CandidateFamily, ...]
) -> tuple[tuple[int, ...], ...]:
    return tuple(
        sorted(
            (tuple(sorted(group)) for group in groups),
            key=lambda group: _group_key(group, families),
        )
    )


def _partition_key(
    partition: tuple[tuple[int, ...], ...], families: tuple[CandidateFamily, ...]
) -> tuple[int, tuple[tuple[str, ...], ...]]:
    return (len(partition), tuple(_group_key(group, families) for group in partition))


def _group_key(group: tuple[int, ...], families: tuple[CandidateFamily, ...]) -> tuple[str, ...]:
    return tuple(sorted(atom.atom_id for index in group for atom in families[index].atoms))


def _package_for_indices(
    indices: tuple[int, ...],
    families: tuple[CandidateFamily, ...],
    constraints: dict[tuple[str, str], PairConstraint],
    policy: OptimizerPolicy,
    version_context: DecisionPackageVersionContext,
) -> DecisionPackage:
    selected_families = tuple(families[index] for index in indices)
    atoms = tuple(atom for family in selected_families for atom in family.atoms)
    pairs = tuple(
        constraints[pair] for pair in combinations(tuple(sorted(atom.atom_id for atom in atoms)), 2)
    )
    package = DecisionPackage(selected_families, pairs, policy, version_context)
    if not package.safe:
        raise OptimizerContractError("optimizer emitted a non-safe package")
    return package


def _attach_outlier_paths(
    manual_families: tuple[CandidateFamily, ...],
    packages: tuple[DecisionPackage, ...],
    outliers: tuple[PackageAtom, ...],
) -> tuple[
    tuple[CandidateFamily, ...],
    tuple[tuple[tuple[CandidateFamily, ...], tuple[PairConstraint, ...]], ...],
]:
    """Attach visible outlier IDs to one deterministic existing result path.

    DecisionPackage-2.0 deliberately keeps outliers out of family membership,
    so it requires their IDs be declared by a package or manual family.
    """
    outlier_ids = tuple(atom.atom_id for atom in outliers)
    manual = tuple(sorted(manual_families, key=lambda family: family.family_id))
    package_parts = tuple((package.families, package.pair_constraints) for package in packages)
    if not outlier_ids:
        return manual, package_parts
    if package_parts:
        families, constraints = package_parts[0]
        first = replace(families[0], outlier_atom_ids=outlier_ids)
        return manual, (((first, *families[1:]), constraints), *package_parts[1:])
    if manual:
        return (replace(manual[0], outlier_atom_ids=outlier_ids), *manual[1:]), package_parts
    raise OptimizerContractError("outlier-only clustering result cannot be represented safely")
