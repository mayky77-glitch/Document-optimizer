"""Regression checks for the exact DecisionPackage-2.0 optimizer."""

from __future__ import annotations

import dataclasses
from itertools import combinations

import pytest

from report_processor.reconciliation_grouping.clustering import ClusteringResult, cluster_atoms
from report_processor.reconciliation_grouping.decision_packages_v2 import (
    AuthoritativePairAttestation,
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
    sha256_fingerprint,
)
from report_processor.reconciliation_grouping.optimizer import (
    OptimizerContractError,
    OptimizerSearchExhausted,
    optimize_packages,
)
from report_processor.reconciliation_patterns import hybrid_retrieval as hybrid
from report_processor.reconciliation_patterns.offline import OutcomeSignature
from report_processor.reconciliation_patterns.pattern_models import PatternVersions


def _ref(token: str) -> str:
    return "sha256:" + (token if len(token) == 64 else token * 64)


def _atom(token: str, *, blockers: tuple[BlockerCode, ...] = ()) -> PackageAtom:
    return PackageAtom(
        semantic_ref=_ref(token),
        atom_version_ref=_ref(token),
        critical_signature_ref=_ref("a"),
        typed_signature_ref=_ref("b"),
        outcome_ref=sha256_fingerprint(OutcomeSignature("accept", "quantity_cost", "category")),
        boundary=PackageBoundary(
            category_ref=sha256_fingerprint("category"),
            mode=PackageMode.QUANTITY_COST,
            unit_compatibility=UnitCompatibility.COMPATIBLE,
            unit_ref=_ref("d"),
            action_ref=_ref("e"),
            object_ref=_ref("f"),
        ),
        manual_blockers=blockers,
    )


def _authority() -> hybrid.AuthorityEnvelope:
    query = hybrid.create_hybrid_query(
        query_ref=_ref("a"),
        tenant_ref=_ref("b"),
        project_ref=_ref("c"),
        document_type_fingerprint=_ref("d"),
        taxonomy_version_fingerprint=_ref("e"),
        scope_fingerprint=_ref("f"),
        consequential_version_fingerprint=_ref("a"),
        embedding_identity_fingerprint=_ref("2"),
        confirmed_source_identity_fingerprint=_ref("3"),
        prototype_source_identity_fingerprint=_ref("4"),
        hard_negative_identity_fingerprint=_ref("5"),
        full_term_fingerprint=_ref("6"),
        skeleton_fingerprint=_ref("7"),
        exact_only=False,
        limit=1,
    )
    return hybrid.resolve_authority(
        query,
        exact_feedback=OutcomeSignature("accept", "quantity_cost", "category"),
        exact_feedback_ref=_ref("8"),
        matched_histories=(),
        current_versions=PatternVersions("Parser-1.0", "Model-1.0", "Taxonomy-1.0"),
    )


def _chain(atom: PackageAtom) -> tuple[hybrid.HybridQuery, hybrid.HybridRetrievalResult]:
    query = hybrid.create_hybrid_query(
        query_ref=atom.semantic_ref,
        tenant_ref=_ref("b"),
        project_ref=_ref("c"),
        document_type_fingerprint=_ref("d"),
        taxonomy_version_fingerprint=_ref("e"),
        scope_fingerprint=_ref("f"),
        consequential_version_fingerprint=_ref("a"),
        embedding_identity_fingerprint=_ref("2"),
        confirmed_source_identity_fingerprint=_ref("3"),
        prototype_source_identity_fingerprint=_ref("4"),
        hard_negative_identity_fingerprint=_ref("5"),
        full_term_fingerprint=_ref("6"),
        skeleton_fingerprint=_ref("7"),
        exact_only=False,
        limit=1,
    )
    authority = hybrid.resolve_authority(
        query,
        exact_feedback=OutcomeSignature("accept", "quantity_cost", "category"),
        exact_feedback_ref=_ref("8"),
        matched_histories=(),
        current_versions=PatternVersions("Parser-1.0", "Model-1.0", "Taxonomy-1.0"),
    )
    return query, hybrid.create_hybrid_retrieval_result(
        query_fingerprint=query.fingerprint,
        status=hybrid.HybridStatus.AUTHORITATIVE_EXACT,
        authority=authority,
        candidates=(),
        hard_negatives=(),
        unavailable_channels=(),
        requires_manual_review=False,
        auto_accepted=False,
    )


def _pair(
    left: PackageAtom,
    right: PackageAtom,
    relation: PairRelation = PairRelation.MUST_LINK,
    *,
    context_ref: str | None = None,
) -> PairConstraint:
    return PairConstraint(
        left.atom_id,
        right.atom_id,
        relation,
        (
            AuthoritativePairAttestation.from_authoritative_results(
                left, *_chain(left), right, *_chain(right), _context(_policy())
            )
            if relation is PairRelation.MUST_LINK
            else None
        ),
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
        authority_context_ref=_authority().consequential_version_fingerprint,
        consequential_refs=(_authority().consequential_version_fingerprint, _ref(ref)),
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

    assert not optimized.packages and not optimized.outlier_atoms
    assert len(optimized.manual_families) == 2


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


def test_cluster_to_optimizer_keeps_the_ab_ac_bd_optimum_available() -> None:
    atoms = tuple(sorted((_atom(str(index)) for index in range(4)), key=lambda atom: atom.atom_id))
    constraints = (
        _pair(atoms[0], atoms[1]),
        _pair(atoms[0], atoms[2]),
        _pair(atoms[1], atoms[3]),
    )
    policy = _policy(atoms=2, families=2, pairs=1)

    optimized = optimize_packages(cluster_atoms(atoms, constraints), policy, _context(policy))

    assert optimized.action_reduction == 2
    assert not optimized.outlier_atoms


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

    assert optimized.manual_families[0].blocker_codes == manual.blocker_codes
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


def test_stale_authority_context_stays_manual_even_when_old_ref_is_retained() -> None:
    first, second = _atom("1"), _atom("2")
    policy = _policy(atoms=2, families=2, pairs=1)
    context = _context(policy)
    stale = dataclasses.replace(
        context,
        authority_context_ref=_ref("b"),
        consequential_refs=(context.authority_context_ref, _ref("b")),
    )
    result = cluster_atoms((first, second), (_pair(first, second),))

    optimized = optimize_packages(result, policy, stale)

    assert not optimized.packages and not optimized.outlier_atoms
    assert optimized.manual_families


def test_search_bound_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    atom = _atom("1")
    policy = _policy(atoms=1, families=1, pairs=0)
    result = _result((atom,), (_family((atom,), ()),), ())
    monkeypatch.setattr("report_processor.reconciliation_grouping.optimizer.MAX_SEARCH_STATES", 0)

    with pytest.raises(OptimizerSearchExhausted, match="search bound"):
        optimize_packages(result, policy, _context(policy))


def test_ids_revisions_and_tie_breaking_are_permutation_invariant() -> None:
    atoms = tuple(_atom(str(index)) for index in range(3))
    context = _context(_policy(), ref="1")
    pairs = tuple(
        _pair(left, right, context_ref=context.fingerprint)
        for left, right in combinations(atoms, 2)
    )
    families = tuple(_family((atom,), pairs) for atom in atoms)
    policy = _policy(atoms=2, families=2, pairs=1)
    baseline = optimize_packages(_result(atoms, families, pairs), policy, context)
    permuted = optimize_packages(
        _result(tuple(reversed(atoms)), tuple(reversed(families)), tuple(reversed(pairs))),
        policy,
        context,
    )
    revised_context = _context(policy, ref="2")
    revised_pairs = tuple(
        _pair(left, right, context_ref=revised_context.fingerprint)
        for left, right in combinations(atoms, 2)
    )
    revised_families = tuple(_family((atom,), revised_pairs) for atom in atoms)
    revised = optimize_packages(
        _result(atoms, revised_families, revised_pairs), policy, revised_context
    )

    assert baseline == permuted
    assert baseline.result_id == permuted.result_id
    assert baseline.result_id == revised.result_id
    assert baseline.fingerprint != revised.fingerprint
