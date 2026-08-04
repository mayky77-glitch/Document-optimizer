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
        unit_ref=_ref("0"),
        action_ref=_ref("b"),
        object_ref=_ref("c"),
    )


def _atom(
    token: str,
    *,
    boundary: contracts.PackageBoundary | None = None,
    blockers: tuple[contracts.BlockerCode, ...] = (),
) -> contracts.PackageAtom:
    return contracts.PackageAtom(
        semantic_ref=_ref(token),
        atom_version_ref=_ref(token),
        critical_signature_ref=_ref("a"),
        typed_signature_ref=_ref("b"),
        boundary=boundary or _boundary(),
        manual_blockers=blockers,
    )


def _policy() -> contracts.OptimizerPolicy:
    return contracts.OptimizerPolicy(
        policy_ref=_ref("d"),
        max_safe_atoms=4,
        max_families=4,
        max_pair_constraints=8,
    )


def _context(
    policy: contracts.OptimizerPolicy,
    refs: tuple[str, ...] = (_ref("1"), _ref("2")),
) -> contracts.DecisionPackageVersionContext:
    return contracts.DecisionPackageVersionContext(
        semantic_contract_version="SemanticSkeleton-1.0",
        feedback_contract_version="FeedbackGraph-1.0",
        clustering_contract_version="ConstrainedClustering-1.0",
        optimizer_policy_version=policy.version,
        consequential_refs=refs,
    )


def _package(
    *,
    unit: contracts.UnitCompatibility = contracts.UnitCompatibility.COMPATIBLE,
    relation: contracts.PairRelation = contracts.PairRelation.MUST_LINK,
    atom_blockers: tuple[contracts.BlockerCode, ...] = (),
    family_blockers: tuple[contracts.BlockerCode, ...] = (),
    pair_blockers: tuple[contracts.BlockerCode, ...] = (),
    max_safe_atoms: int = 4,
    context: contracts.DecisionPackageVersionContext | None = None,
) -> contracts.DecisionPackage:
    atoms = (
        _atom("e", boundary=_boundary(unit=unit), blockers=atom_blockers),
        _atom("f", boundary=_boundary(unit=unit)),
    )
    constraint = contracts.PairConstraint(
        atoms[1].atom_id,
        atoms[0].atom_id,
        relation,
        evidence_refs=(_ref("9"), _ref("8")),
        blocker_codes=pair_blockers,
    )
    family = contracts.CandidateFamily(atoms[::-1], (constraint,), family_blockers)
    policy = dataclasses.replace(_policy(), max_safe_atoms=max_safe_atoms)
    return contracts.DecisionPackage((family,), (constraint,), policy, context or _context(policy))


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


def test_boundary_and_atom_bind_opaque_unit_and_group_version() -> None:
    boundary = _boundary()
    atom = _atom("e")
    assert boundary.unit_ref == _ref("0")
    assert atom.atom_version_ref == _ref("e")
    assert atom.critical_signature_ref == _ref("a")
    assert atom.typed_signature_ref == _ref("b")
    with pytest.raises(contracts.DecisionPackageContractError):
        dataclasses.replace(boundary, unit_ref="metres")
    with pytest.raises(contracts.DecisionPackageContractError):
        dataclasses.replace(atom, atom_version_ref="group-v2")
    with pytest.raises(contracts.DecisionPackageContractError):
        dataclasses.replace(atom, critical_signature_ref="critical modifiers")
    with pytest.raises(contracts.DecisionPackageContractError):
        dataclasses.replace(atom, typed_signature_ref="typed slots")
    with pytest.raises(contracts.DecisionPackageContractError):
        _atom("e", blockers=(contracts.BlockerCode.MANUAL_REVIEW,) * 2)


def test_canonical_ids_and_fingerprints_are_input_order_independent() -> None:
    package = _package()
    reversed_package = _package()
    assert package.pair_constraints[0].left_atom_id < package.pair_constraints[0].right_atom_id
    assert package.pair_constraints[0].evidence_refs == (_ref("8"), _ref("9"))
    assert package.fingerprint == reversed_package.fingerprint
    assert package.package_id.endswith(package.identity_fingerprint.removeprefix("sha256:"))
    assert package.safe is True
    result = contracts.DecisionPackageResult((package,), package.policy, package.version_context)
    assert result.result_id.endswith(result.identity_fingerprint.removeprefix("sha256:"))


@pytest.mark.parametrize(
    ("unit", "relation", "atom_blockers", "family_blockers", "pair_blockers", "limit"),
    (
        (contracts.UnitCompatibility.EXACT_ONLY, contracts.PairRelation.MUST_LINK, (), (), (), 4),
        (contracts.UnitCompatibility.UNKNOWN, contracts.PairRelation.MUST_LINK, (), (), (), 4),
        (contracts.UnitCompatibility.COMPATIBLE, contracts.PairRelation.CANNOT_LINK, (), (), (), 4),
        (
            contracts.UnitCompatibility.COMPATIBLE,
            contracts.PairRelation.MANUAL_REVIEW,
            (),
            (),
            (),
            4,
        ),
        (
            contracts.UnitCompatibility.COMPATIBLE,
            contracts.PairRelation.MUST_LINK,
            (contracts.BlockerCode.MANUAL_REVIEW,),
            (),
            (),
            4,
        ),
        (
            contracts.UnitCompatibility.COMPATIBLE,
            contracts.PairRelation.MUST_LINK,
            (),
            (contracts.BlockerCode.MANUAL_REVIEW,),
            (),
            4,
        ),
        (
            contracts.UnitCompatibility.COMPATIBLE,
            contracts.PairRelation.MUST_LINK,
            (),
            (),
            (contracts.BlockerCode.CANNOT_LINK,),
            4,
        ),
        (contracts.UnitCompatibility.COMPATIBLE, contracts.PairRelation.MUST_LINK, (), (), (), 1),
    ),
)
def test_safe_requires_all_explicit_hard_invariants(
    unit: contracts.UnitCompatibility,
    relation: contracts.PairRelation,
    atom_blockers: tuple[contracts.BlockerCode, ...],
    family_blockers: tuple[contracts.BlockerCode, ...],
    pair_blockers: tuple[contracts.BlockerCode, ...],
    limit: int,
) -> None:
    assert (
        _package(
            unit=unit,
            relation=relation,
            atom_blockers=atom_blockers,
            family_blockers=family_blockers,
            pair_blockers=pair_blockers,
            max_safe_atoms=limit,
        ).safe
        is False
    )


def test_context_requires_ordered_consequential_refs_and_stales_revision_only() -> None:
    policy = _policy()
    with pytest.raises(contracts.DecisionPackageContractError):
        _context(policy, ())
    with pytest.raises(contracts.DecisionPackageContractError):
        _context(policy, (_ref("1"), _ref("1")))
    initial = _package(context=_context(policy, (_ref("2"), _ref("1"))))
    changed = _package(context=_context(policy, (_ref("3"), _ref("1"))))
    assert initial.version_context.consequential_refs == (_ref("1"), _ref("2"))
    assert initial.package_id == changed.package_id
    assert initial.fingerprint != changed.fingerprint


def test_pair_constraints_require_full_ids_and_controlled_opaque_evidence() -> None:
    package = _package()
    with pytest.raises(contracts.DecisionPackageContractError):
        contracts.PairConstraint(
            "package-atom-short",
            package.atoms[0].atom_id,
            contracts.PairRelation.MUST_LINK,
        )
    with pytest.raises(contracts.DecisionPackageContractError):
        contracts.PairConstraint(
            package.atoms[0].atom_id,
            package.atoms[1].atom_id,
            contracts.PairRelation.MUST_LINK,
            evidence_refs=("operator note",),
        )
    with pytest.raises(contracts.DecisionPackageContractError):
        contracts.PairConstraint(
            package.atoms[0].atom_id,
            package.atoms[1].atom_id,
            contracts.PairRelation.MUST_LINK,
            blocker_codes=(contracts.BlockerCode.OUTLIER,) * 2,
        )
    unattested = contracts.PairConstraint(
        package.atoms[0].atom_id,
        package.atoms[1].atom_id,
        contracts.PairRelation.MUST_LINK,
    )
    assert unattested.is_compatible is False
    unattested_family = contracts.CandidateFamily(package.atoms, (unattested,))
    assert (
        contracts.DecisionPackage(
            (unattested_family,),
            (unattested,),
            package.policy,
            package.version_context,
        ).safe
        is False
    )


def test_manual_family_and_outlier_paths_are_visible_and_disjoint() -> None:
    package = _package()
    outlier = _atom("7")
    manual = contracts.CandidateFamily(
        (_atom("6"),),
        blocker_codes=(contracts.BlockerCode.MANUAL_REVIEW,),
        outlier_atom_ids=(outlier.atom_id,),
    )
    result = contracts.DecisionPackageResult(
        (package,),
        package.policy,
        package.version_context,
        manual_families=(manual,),
        outlier_atoms=(outlier,),
        blocker_codes=(contracts.BlockerCode.MANUAL_REVIEW,),
    )
    assert result.manual_family_ids == (manual.family_id,)
    assert result.outlier_atom_ids == (outlier.atom_id,)
    with pytest.raises(contracts.DecisionPackageContractError):
        contracts.DecisionPackageResult(
            (package,),
            package.policy,
            package.version_context,
            manual_families=(manual,),
            outlier_atoms=(package.atoms[0],),
        )


def test_result_rejects_duplicate_atom_membership_between_packages_and_manual_paths() -> None:
    package = _package()
    duplicate_manual = contracts.CandidateFamily(
        (package.atoms[0],),
        blocker_codes=(contracts.BlockerCode.MANUAL_REVIEW,),
    )
    with pytest.raises(contracts.DecisionPackageContractError):
        contracts.DecisionPackageResult(
            (package,),
            package.policy,
            package.version_context,
            manual_families=(duplicate_manual,),
        )
    with pytest.raises(contracts.DecisionPackageContractError):
        overlapping_atom = _atom("7")
        overlap_constraint = contracts.PairConstraint(
            package.atoms[0].atom_id,
            overlapping_atom.atom_id,
            contracts.PairRelation.MUST_LINK,
        )
        overlap_family = contracts.CandidateFamily(
            (package.atoms[0], overlapping_atom),
            (overlap_constraint,),
        )
        overlap_package = contracts.DecisionPackage(
            (overlap_family,),
            (overlap_constraint,),
            package.policy,
            package.version_context,
        )
        contracts.DecisionPackageResult(
            (package, overlap_package),
            package.policy,
            package.version_context,
        )


def test_rejects_duplicate_semantic_membership_with_distinct_atom_versions() -> None:
    first = _atom("7")
    changed_version = dataclasses.replace(first, atom_version_ref=_ref("8"))
    with pytest.raises(contracts.DecisionPackageContractError):
        contracts.CandidateFamily((first, changed_version))

    package = _package()
    left = contracts.CandidateFamily((first,))
    right = contracts.CandidateFamily((changed_version,))
    with pytest.raises(contracts.DecisionPackageContractError):
        contracts.DecisionPackage((left, right), (), package.policy, package.version_context)

    outlier = dataclasses.replace(package.atoms[0], atom_version_ref=_ref("7"))
    manual = contracts.CandidateFamily(
        (_atom("6"),),
        blocker_codes=(contracts.BlockerCode.OUTLIER,),
        outlier_atom_ids=(outlier.atom_id,),
    )
    with pytest.raises(contracts.DecisionPackageContractError):
        contracts.DecisionPackageResult(
            (package,),
            package.policy,
            package.version_context,
            manual_families=(manual,),
            outlier_atoms=(outlier,),
        )


def test_action_reduction_is_deterministic_and_counts_safe_packages_only() -> None:
    safe = _package()
    assert safe.action_reduction == 1
    unsafe_atoms = (_atom("6"), _atom("7"))
    unattested = contracts.PairConstraint(
        unsafe_atoms[0].atom_id,
        unsafe_atoms[1].atom_id,
        contracts.PairRelation.MUST_LINK,
    )
    unsafe_family = contracts.CandidateFamily(unsafe_atoms, (unattested,))
    unsafe = contracts.DecisionPackage(
        (unsafe_family,),
        (unattested,),
        safe.policy,
        safe.version_context,
    )
    assert unsafe.action_reduction == 1 and unsafe.safe is False
    result = contracts.DecisionPackageResult(
        (unsafe, safe),
        safe.policy,
        safe.version_context,
    )
    assert result.action_reduction == safe.action_reduction


def test_rejects_unknown_boundary_and_float_or_raw_values() -> None:
    atom = _atom("e", boundary=dataclasses.replace(_boundary(), category_ref=None))
    family = contracts.CandidateFamily((atom,))
    policy = _policy()
    assert contracts.DecisionPackage((family,), (), policy, _context(policy)).safe is False
    with pytest.raises(contracts.DecisionPackageContractError):
        contracts.canonical_json_bytes((1.0,))
    with pytest.raises(contracts.DecisionPackageContractError):
        contracts.canonical_json_bytes({_ref("a")})
