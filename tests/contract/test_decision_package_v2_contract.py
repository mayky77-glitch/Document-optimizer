"""Contract checks for inert DecisionPackage-2.0 DTOs."""

from __future__ import annotations

import dataclasses

import pytest

from report_processor.reconciliation_grouping import decision_packages_v2 as contracts


def _ref(token: str) -> str:
    return "sha256:" + token * 64


def _boundary(
    *, unit: contracts.UnitCompatibility = contracts.UnitCompatibility.COMPATIBLE
) -> contracts.PackageBoundary:
    return contracts.PackageBoundary(
        category_ref=_ref("a"),
        mode=contracts.PackageMode.QUANTITY_COST,
        unit_compatibility=unit,
        action_ref=_ref("b"),
        object_ref=_ref("c"),
    )


def _policy() -> contracts.OptimizerPolicy:
    return contracts.OptimizerPolicy(
        policy_ref=_ref("d"),
        max_safe_atoms=4,
        max_families=4,
        max_pair_constraints=8,
    )


def _context(policy: contracts.OptimizerPolicy) -> contracts.DecisionPackageVersionContext:
    return contracts.DecisionPackageVersionContext(
        semantic_contract_version="SemanticSkeleton-1.0",
        feedback_contract_version="FeedbackGraph-1.0",
        clustering_contract_version="ConstrainedClustering-1.0",
        optimizer_policy_version=policy.version,
    )


def _package(
    *,
    unit: contracts.UnitCompatibility = contracts.UnitCompatibility.COMPATIBLE,
    relation: contracts.PairRelation = contracts.PairRelation.MUST_LINK,
    manual: bool = False,
    max_safe_atoms: int = 4,
) -> contracts.DecisionPackage:
    atoms = (
        contracts.PackageAtom(_ref("e"), _boundary(unit=unit)),
        contracts.PackageAtom(_ref("f"), _boundary(unit=unit)),
    )
    constraint = contracts.PairConstraint(atoms[1].atom_id, atoms[0].atom_id, relation)
    family = contracts.CandidateFamily(atoms[::-1], (constraint,), manual)
    policy = dataclasses.replace(_policy(), max_safe_atoms=max_safe_atoms)
    return contracts.DecisionPackage((family,), (constraint,), policy, _context(policy))


def test_public_models_are_frozen_slotted_and_versioned() -> None:
    assert contracts.DECISION_PACKAGE_VERSION == "DecisionPackage-2.0"
    for model in (
        contracts.PackageBoundary,
        contracts.PackageAtom,
        contracts.PairConstraint,
        contracts.CandidateFamily,
        contracts.OptimizerPolicy,
        contracts.DecisionPackageVersionContext,
        contracts.DecisionPackage,
        contracts.DecisionPackageResult,
    ):
        assert model.__dataclass_params__.frozen
        assert "__slots__" in vars(model)


def test_canonical_ids_and_fingerprints_are_input_order_independent() -> None:
    package = _package()
    reversed_package = _package()
    assert package.pair_constraints[0].left_atom_id < package.pair_constraints[0].right_atom_id
    assert package.fingerprint == reversed_package.fingerprint
    assert package.package_id.endswith(package.fingerprint.removeprefix("sha256:"))
    assert package.safe is True
    result = contracts.DecisionPackageResult((package,), package.policy, package.version_context)
    assert result.result_id.endswith(result.fingerprint.removeprefix("sha256:"))


@pytest.mark.parametrize(
    ("unit", "relation", "manual", "limit"),
    (
        (contracts.UnitCompatibility.EXACT_ONLY, contracts.PairRelation.MUST_LINK, False, 4),
        (contracts.UnitCompatibility.UNKNOWN, contracts.PairRelation.MUST_LINK, False, 4),
        (contracts.UnitCompatibility.COMPATIBLE, contracts.PairRelation.CANNOT_LINK, False, 4),
        (contracts.UnitCompatibility.COMPATIBLE, contracts.PairRelation.MANUAL_REVIEW, False, 4),
        (contracts.UnitCompatibility.COMPATIBLE, contracts.PairRelation.MUST_LINK, True, 4),
        (contracts.UnitCompatibility.COMPATIBLE, contracts.PairRelation.MUST_LINK, False, 1),
    ),
)
def test_safe_requires_all_explicit_hard_invariants(
    unit: contracts.UnitCompatibility,
    relation: contracts.PairRelation,
    manual: bool,
    limit: int,
) -> None:
    assert _package(unit=unit, relation=relation, manual=manual, max_safe_atoms=limit).safe is False


def test_safe_rejects_unknown_boundary_and_incomplete_pair_coverage() -> None:
    atom = contracts.PackageAtom(
        _ref("e"),
        dataclasses.replace(_boundary(), category_ref=None),
    )
    family = contracts.CandidateFamily((atom,))
    policy = _policy()
    package = contracts.DecisionPackage((family,), (), policy, _context(policy))
    assert package.safe is False

    atoms = (
        contracts.PackageAtom(_ref("e"), _boundary()),
        contracts.PackageAtom(_ref("f"), _boundary()),
    )
    family = contracts.CandidateFamily(atoms)
    package = contracts.DecisionPackage((family,), (), policy, _context(policy))
    assert package.safe is False


def test_rejects_nonopaque_and_duplicate_or_out_of_scope_values() -> None:
    with pytest.raises(contracts.DecisionPackageContractError):
        contracts.PackageAtom("raw source term", _boundary())
    with pytest.raises(contracts.DecisionPackageContractError):
        contracts.CandidateFamily((_package().atoms[0], _package().atoms[0]))
    package = _package()
    outsider = contracts.PackageAtom(_ref("0"), _boundary())
    with pytest.raises(contracts.DecisionPackageContractError):
        contracts.DecisionPackage(
            package.families,
            (
                contracts.PairConstraint(
                    package.atoms[0].atom_id,
                    outsider.atom_id,
                    contracts.PairRelation.MUST_LINK,
                ),
            ),
            package.policy,
            package.version_context,
        )


def test_canonical_json_rejects_floats_and_unsupported_values() -> None:
    with pytest.raises(contracts.DecisionPackageContractError):
        contracts.canonical_json_bytes((1.0,))
    with pytest.raises(contracts.DecisionPackageContractError):
        contracts.canonical_json_bytes({_ref("a")})
