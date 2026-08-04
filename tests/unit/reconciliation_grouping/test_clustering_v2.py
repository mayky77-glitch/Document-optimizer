"""Regression checks for complete-linkage DecisionPackage-2.0 clustering."""

from __future__ import annotations

import dataclasses
from itertools import combinations

import pytest

from report_processor.reconciliation_grouping.clustering import (
    CLUSTERING_VERSION,
    MAX_CLUSTERING_ATOMS,
    ClusteringContractError,
    ClusteringResult,
    cluster_atoms,
)
from report_processor.reconciliation_grouping.decision_packages_v2 import (
    BlockerCode,
    CandidateFamily,
    PackageAtom,
    PackageBoundary,
    PackageMode,
    PairConstraint,
    PairRelation,
    UnitCompatibility,
)


def _ref(token: str) -> str:
    return "sha256:" + (token if len(token) == 64 else token * 64)


def _boundary(
    *,
    category: str | None = "a",
    mode: PackageMode | None = PackageMode.QUANTITY_COST,
    unit: UnitCompatibility = UnitCompatibility.COMPATIBLE,
    action: str | None = "b",
    object_ref: str | None = "c",
) -> PackageBoundary:
    return PackageBoundary(
        category_ref=_ref(category) if category else None,
        mode=mode,
        unit_compatibility=unit,
        unit_ref=_ref("0"),
        action_ref=_ref(action) if action else None,
        object_ref=_ref(object_ref) if object_ref else None,
    )


def _atom(
    token: str,
    *,
    boundary: PackageBoundary | None = None,
    critical: str = "d",
    typed: str = "e",
    blockers: tuple[BlockerCode, ...] = (),
) -> PackageAtom:
    return PackageAtom(
        semantic_ref=_ref(token),
        atom_version_ref=_ref(token),
        critical_signature_ref=_ref(critical),
        typed_signature_ref=_ref(typed),
        boundary=boundary or _boundary(),
        manual_blockers=blockers,
    )


def _pair(
    left: PackageAtom,
    right: PackageAtom,
    relation: PairRelation = PairRelation.MUST_LINK,
    *,
    attested: bool = True,
) -> PairConstraint:
    return PairConstraint(
        left.atom_id,
        right.atom_id,
        relation,
        evidence_refs=(_ref("f"),) if attested else (),
    )


def test_complete_linkage_blocks_the_transitive_chain_trap() -> None:
    atoms = tuple(sorted((_atom("1"), _atom("2"), _atom("3")), key=lambda atom: atom.atom_id))
    constraints = (_pair(atoms[0], atoms[1]), _pair(atoms[1], atoms[2]))

    result = cluster_atoms(atoms, constraints)

    assert [family.atom_ids for family in result.candidate_families] == [
        (atoms[0].atom_id, atoms[1].atom_id)
    ]
    assert result.outlier_atom_ids == (atoms[2].atom_id,)
    assert not result.manual_families


def test_direct_cannot_link_and_missing_pair_stay_manual() -> None:
    first, second = _atom("1"), _atom("2")
    cannot = cluster_atoms((first, second), (_pair(first, second, PairRelation.CANNOT_LINK),))
    missing = cluster_atoms((first, second), ())

    assert not cannot.candidate_families and not cannot.outlier_atoms
    assert cannot.manual_families[0].blocker_codes == (BlockerCode.CANNOT_LINK,)
    assert not missing.candidate_families and not missing.outlier_atoms
    assert missing.manual_families[0].blocker_codes == (BlockerCode.PATTERN_UNATTESTED,)


@pytest.mark.parametrize(
    "unit",
    (UnitCompatibility.UNKNOWN, UnitCompatibility.EXACT_ONLY, UnitCompatibility.INCOMPATIBLE),
)
def test_unknown_and_noncompatible_units_never_make_safe_candidates(
    unit: UnitCompatibility,
) -> None:
    first = _atom("1", boundary=_boundary(unit=unit))
    second = _atom("2", boundary=_boundary(unit=unit))

    result = cluster_atoms((first, second), (_pair(first, second),))

    assert not result.candidate_families
    assert result.manual_families[0].blocker_codes == (BlockerCode.PATTERN_UNATTESTED,)


@pytest.mark.parametrize("missing", ("action", "object"))
def test_unknown_work_is_manual(missing: str) -> None:
    boundary = _boundary(action=None) if missing == "action" else _boundary(object_ref=None)
    first, second = _atom("1", boundary=boundary), _atom("2", boundary=boundary)

    result = cluster_atoms((first, second), (_pair(first, second),))

    assert not result.candidate_families
    assert result.manual_families[0].blocker_codes == (BlockerCode.MANUAL_REVIEW,)


def test_exact_boundaries_and_signatures_split_without_forcing_manual() -> None:
    first = _atom("1", critical="d", typed="e")
    second = _atom("2", critical="f", typed="e")
    third = _atom("3", critical="d", typed="f")
    other_boundary = _atom("4", boundary=_boundary(category="9"))
    all_pairs = tuple(_pair(left, right) for left, right in combinations((first, second, third), 2))

    result = cluster_atoms((other_boundary, third, second, first), all_pairs)

    assert {family.atom_ids for family in result.candidate_families} == {
        (first.atom_id,),
        (second.atom_id,),
        (third.atom_id,),
        (other_boundary.atom_id,),
    }
    assert not result.manual_families and not result.outlier_atoms


def test_incompatible_outlier_leaves_the_compatible_remainder_safe_and_visible() -> None:
    first, second, outlier = _atom("1"), _atom("2"), _atom("3")
    result = cluster_atoms(
        (first, second, outlier),
        (
            _pair(first, second),
            _pair(first, outlier, PairRelation.CANNOT_LINK),
            _pair(second, outlier, PairRelation.CANNOT_LINK),
        ),
    )

    assert result.candidate_families[0].atom_ids == tuple(sorted((first.atom_id, second.atom_id)))
    assert result.outlier_atom_ids == (outlier.atom_id,)
    assert result.outlier_semantic_refs == (outlier.semantic_ref,)
    assert not result.manual_families


def test_result_is_permutation_invariant_and_uses_stable_ids() -> None:
    first, second, third = _atom("1"), _atom("2"), _atom("3")
    constraints = (_pair(first, second), _pair(first, third), _pair(second, third))

    baseline = cluster_atoms((first, second, third), constraints)
    permuted = cluster_atoms(tuple(reversed((first, second, third))), tuple(reversed(constraints)))

    assert baseline == permuted
    assert baseline.candidate_families[0].family_id == permuted.candidate_families[0].family_id
    assert baseline.version == CLUSTERING_VERSION


def test_duplicate_or_foreign_constraints_are_rejected_without_echoing_input() -> None:
    first, second, foreign = _atom("1"), _atom("2"), _atom("3")
    duplicate = _pair(first, second)
    foreign_constraint = _pair(first, foreign)

    with pytest.raises(ClusteringContractError, match="constraints must be unique"):
        cluster_atoms((first, second), (duplicate, duplicate))
    with pytest.raises(ClusteringContractError, match="reference input atoms"):
        cluster_atoms((first, second), (foreign_constraint,))


def test_result_rejects_duplicate_semantic_membership_and_foreign_constraints() -> None:
    first = _atom("1")
    changed_version = dataclasses.replace(first, atom_version_ref=_ref("2"))
    manual = CandidateFamily((changed_version,), blocker_codes=(BlockerCode.MANUAL_REVIEW,))
    foreign = _atom("3")

    with pytest.raises(ClusteringContractError, match="semantic membership"):
        ClusteringResult((CandidateFamily((first,)),), (manual,))
    with pytest.raises(ClusteringContractError, match="reference result atoms"):
        ClusteringResult((CandidateFamily((first,)),), pair_constraints=(_pair(first, foreign),))


def test_contract_shape_is_frozen_slotted_and_never_accepts_raw_values() -> None:
    assert ClusteringResult.__dataclass_params__.frozen
    assert "__slots__" in vars(ClusteringResult)
    with pytest.raises(ClusteringContractError, match="contract atoms"):
        cluster_atoms(("raw work name",), ())  # type: ignore[arg-type]


def test_input_atom_bound_is_enforced() -> None:
    atoms = tuple(_atom(f"{index:064x}") for index in range(MAX_CLUSTERING_ATOMS + 1))

    with pytest.raises(ClusteringContractError, match="atom count is out of bounds"):
        cluster_atoms(atoms, ())
