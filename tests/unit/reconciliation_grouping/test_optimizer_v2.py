"""Regression checks for the exact DecisionPackage-2.0 optimizer."""

from __future__ import annotations

import dataclasses
from itertools import combinations

import pytest

from report_processor.reconciliation_grouping.clustering import ClusteringResult
from report_processor.reconciliation_grouping.decision_packages_v2 import (
    BlockerCode,
    CandidateFamily,
    DecisionPackageVersionContext,
    OptimizerPolicy,
    PackageAtom,
    PackageBoundary,
    PackageMode,
    PairConstraint,
    PairRelation,
    UnitCompatibility,
)
from report_processor.reconciliation_grouping.optimizer import (
    OptimizerContractError,
    OptimizerSearchExhausted,
    optimize_packages,
)


def _ref(token: str) -> str:
    return "sha256:" + (token if len(token) == 64 else token * 64)


def _atom(token: str, *, blockers: tuple[BlockerCode, ...] = ()) -> PackageAtom:
    return PackageAtom(
        semantic_ref=_ref(token),
        atom_version_ref=_ref(token),
        critical_signature_ref=_ref("a"),
        typed_signature_ref=_ref("b"),
        boundary=PackageBoundary(
            category_ref=_ref("c"),
            mode=PackageMode.QUANTITY_COST,
            unit_compatibility=UnitCompatibility.COMPATIBLE,
            unit_ref=_ref("d"),
            action_ref=_ref("e"),
            object_ref=_ref("f"),
        ),
        manual_blockers=blockers,
    )


def _pair(
    left: PackageAtom, right: PackageAtom, relation: PairRelation = PairRelation.MUST_LINK
) -> PairConstraint:
    return PairConstraint(
        left.atom_id,
        right.atom_id,
        relation,
        evidence_refs=(_ref("9"),) if relation is PairRelation.MUST_LINK else (),
    )


def _family(atoms: tuple[PackageAtom, ...], pairs: tuple[PairConstraint, ...]) -> CandidateFamily:
    atom_ids = {atom.atom_id for atom in atoms}
    return CandidateFamily(
        atoms,
        tuple(pair for pair in pairs if set(pair.pair_key) <= atom_ids),
    )


def _policy(*, atoms: int = 4, families: int = 4, pairs: int = 8) -> OptimizerPolicy:
    return OptimizerPolicy(_ref("0"), atoms, families, pairs)


def _context(policy: OptimizerPolicy, *, ref: str = "1") -> DecisionPackageVersionContext:
    return DecisionPackageVersionContext(
        semantic_contract_version="SemanticSkeleton-1.0",
        feedback_contract_version="FeedbackGraph-1.0",
        clustering_contract_version="ConstrainedClustering-1.0",
        optimizer_policy_version=policy.version,
        consequential_refs=(_ref(ref),),
    )


def _result(
    atoms: tuple[PackageAtom, ...],
    families: tuple[CandidateFamily, ...],
    constraints: tuple[PairConstraint, ...],
    *,
    manual: tuple[CandidateFamily, ...] = (),
    outliers: tuple[PackageAtom, ...] = (),
) -> ClusteringResult:
    assert {atom.atom_id for family in (*families, *manual) for atom in family.atoms} | {
        atom.atom_id for atom in outliers
    } == {atom.atom_id for atom in atoms}
    return ClusteringResult(families, manual, outliers, constraints)


def test_oversized_complete_family_splits_at_policy_limit_deterministically() -> None:
    atoms = tuple(sorted((_atom(str(index)) for index in range(4)), key=lambda atom: atom.atom_id))
    pairs = tuple(_pair(left, right) for left, right in combinations(atoms, 2))
    family = _family(atoms, pairs)
    policy = _policy(atoms=2, families=1, pairs=1)

    baseline = optimize_packages(_result(atoms, (family,), pairs), policy, _context(policy))
    permuted = optimize_packages(
        _result(tuple(reversed(atoms)), (family,), tuple(reversed(pairs))), policy, _context(policy)
    )

    assert [len(package.atoms) for package in baseline.packages] == [2, 2]
    assert all(package.safe for package in baseline.packages)
    assert baseline == permuted


def test_compatible_families_pack_with_full_cross_pair_coverage() -> None:
    atoms = tuple(_atom(str(index)) for index in range(4))
    pairs = tuple(_pair(left, right) for left, right in combinations(atoms, 2))
    result = _result(atoms, (_family(atoms[:2], pairs), _family(atoms[2:], pairs)), pairs)
    policy = _policy(atoms=4, families=2, pairs=6)

    optimized = optimize_packages(result, policy, _context(policy))

    assert len(optimized.packages) == 1
    assert optimized.packages[0].safe is True
    assert optimized.action_reduction == 3


@pytest.mark.parametrize("relation", (None, PairRelation.CANNOT_LINK))
def test_cross_family_missing_or_cannot_link_never_becomes_safe(
    relation: PairRelation | None,
) -> None:
    first, second = _atom("1"), _atom("2")
    constraints = () if relation is None else (_pair(first, second, relation),)
    result = _result(
        (first, second),
        (_family((first,), constraints), _family((second,), constraints)),
        constraints,
    )
    policy = _policy(atoms=2, families=2, pairs=1)

    optimized = optimize_packages(result, policy, _context(policy))

    assert len(optimized.packages) == 2
    assert optimized.action_reduction == 0
    assert all(package.safe for package in optimized.packages)


def test_exact_search_beats_the_adversarial_first_fit_trap() -> None:
    atoms = tuple(sorted((_atom(str(index)) for index in range(4)), key=lambda atom: atom.atom_id))
    pairs = (
        _pair(atoms[0], atoms[1]),
        _pair(atoms[0], atoms[2]),
        _pair(atoms[1], atoms[3]),
    )
    families = tuple(_family((atom,), pairs) for atom in atoms)
    policy = _policy(atoms=2, families=2, pairs=1)

    optimized = optimize_packages(_result(atoms, families, pairs), policy, _context(policy))

    assert len(optimized.packages) == 2
    assert optimized.action_reduction == 2
    assert {package.atom_ids for package in optimized.packages} == {
        (atoms[0].atom_id, atoms[2].atom_id),
        (atoms[1].atom_id, atoms[3].atom_id),
    }


def test_manual_and_outlier_paths_propagate_disjointly_with_controlled_blocker() -> None:
    safe, manual_atom, outlier = _atom("1"), _atom("2"), _atom("3")
    manual = CandidateFamily((manual_atom,), blocker_codes=(BlockerCode.MANUAL_REVIEW,))
    result = _result(
        (safe, manual_atom, outlier),
        (_family((safe,), ()),),
        (),
        manual=(manual,),
        outliers=(outlier,),
    )
    policy = _policy(atoms=1, families=1, pairs=0)

    optimized = optimize_packages(result, policy, _context(policy))

    assert optimized.manual_families == (manual,)
    assert optimized.outlier_atoms == (outlier,)
    assert BlockerCode.OUTLIER in optimized.blocker_codes
    memberships = (
        [atom.atom_id for package in optimized.packages for atom in package.atoms]
        + [atom.atom_id for family in optimized.manual_families for atom in family.atoms]
        + [atom.atom_id for atom in optimized.outlier_atoms]
    )
    assert len(memberships) == len(set(memberships))


def test_policy_context_mismatch_and_raw_input_fail_closed() -> None:
    atom = _atom("1")
    policy = _policy(atoms=1, families=1, pairs=0)
    context = dataclasses.replace(_context(policy), optimizer_policy_version="OtherPolicy-1.0")
    result = _result((atom,), (_family((atom,), ()),), ())

    with pytest.raises(OptimizerContractError, match="policy and version context"):
        optimize_packages(result, policy, context)
    with pytest.raises(OptimizerContractError, match="clustering result must be controlled"):
        optimize_packages("raw text", policy, _context(policy))  # type: ignore[arg-type]


def test_search_bound_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    atom = _atom("1")
    policy = _policy(atoms=1, families=1, pairs=0)
    result = _result((atom,), (_family((atom,), ()),), ())
    monkeypatch.setattr("report_processor.reconciliation_grouping.optimizer.MAX_SEARCH_STATES", 0)

    with pytest.raises(OptimizerSearchExhausted, match="search bound"):
        optimize_packages(result, policy, _context(policy))


def test_ids_revisions_and_tie_breaking_are_permutation_invariant() -> None:
    atoms = tuple(_atom(str(index)) for index in range(3))
    pairs = tuple(_pair(left, right) for left, right in combinations(atoms, 2))
    families = tuple(_family((atom,), pairs) for atom in atoms)
    policy = _policy(atoms=2, families=2, pairs=1)
    baseline = optimize_packages(_result(atoms, families, pairs), policy, _context(policy, ref="1"))
    permuted = optimize_packages(
        _result(tuple(reversed(atoms)), tuple(reversed(families)), tuple(reversed(pairs))),
        policy,
        _context(policy, ref="1"),
    )
    revised = optimize_packages(_result(atoms, families, pairs), policy, _context(policy, ref="2"))

    assert baseline == permuted
    assert baseline.result_id == permuted.result_id
    assert baseline.result_id == revised.result_id
    assert baseline.fingerprint != revised.fingerprint
