"""Tests for Wave 4's pure explicit-authority feedback graph."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

from report_processor.reconciliation_patterns import feedback_graph as graph
from report_processor.reconciliation_patterns import offline
from report_processor.reconciliation_patterns import pattern_models as models
from report_processor.reconciliation_patterns import pattern_registry as registry


def _hash(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


def _versions() -> models.PatternVersions:
    return models.PatternVersions("Parser-1.0", "Model-1.0", "Taxonomy-1.0")


def _record(
    name: str, *, target_category: str = "target", scope_category: str = "scope"
) -> models.PatternRecord:
    scope = offline.PatternScope(
        scope_category, "quantity_cost", "unit", "action", "object", "document"
    )
    proposal = offline.IncludeExcludeProposal(f"predicate-{name}", "accept")
    candidate_id = offline.fingerprint(
        {
            "version": offline.PATTERN_CANDIDATE_VERSION,
            "kind": offline.CandidateKind.INCLUDE_EXCLUDE.value,
            "scope": scope,
            "proposal": proposal,
        }
    )
    support = offline.SupportSummary(
        2, 2, 2, 2, 0, tuple(sorted((_hash(name + "-a"), _hash(name + "-b"))))
    )
    candidate = offline.PatternCandidate(
        "candidate",
        candidate_id,
        offline.CandidateKind.INCLUDE_EXCLUDE,
        scope,
        proposal,
        offline.OutcomeSignature("accept", "quantity_cost", target_category),
        support,
        (),
        offline.fingerprint({"candidate_id": candidate_id, "support": support, "risks": ()}),
    )
    return registry.register_candidate(
        candidate, versions=_versions(), actor_ref=_hash("miner")
    ).head


def _provenance(
    source: models.FeedbackEndpoint, target: models.FeedbackEndpoint
) -> models.FeedbackProvenance:
    confirmations = tuple(
        sorted(
            (
                models.FeedbackConfirmation(
                    _hash("confirm-source-" + source.pattern_id),
                    _hash("document-source-" + source.pattern_id),
                    _hash("apply-source-" + source.pattern_id),
                    _hash("result-source-" + source.pattern_id),
                    source.outcome,
                ),
                models.FeedbackConfirmation(
                    _hash("confirm-target-" + target.pattern_id),
                    _hash("document-target-" + target.pattern_id),
                    _hash("apply-target-" + target.pattern_id),
                    _hash("result-target-" + target.pattern_id),
                    target.outcome,
                ),
            ),
            key=lambda item: item.confirmation_ref,
        )
    )
    return models.FeedbackProvenance(
        confirmations,
        tuple(sorted(item.document_set_ref for item in confirmations)),
        tuple(sorted(item.apply_fingerprint for item in confirmations)),
        tuple(sorted(item.result_fingerprint for item in confirmations)),
    )


def _edge(
    relation: models.FeedbackRelation,
    source_record: models.PatternRecord,
    target_record: models.PatternRecord,
) -> models.FeedbackEdge:
    source = models.FeedbackEndpoint(
        source_record.pattern_id, source_record.candidate_id, source_record.expected_outcome
    )
    target = models.FeedbackEndpoint(
        target_record.pattern_id, target_record.candidate_id, target_record.expected_outcome
    )
    assert source.outcome is not None and target.outcome is not None
    reason = (
        models.FeedbackReason.EXPLICIT_AUTHORITATIVE_CONFIRMATION
        if relation is models.FeedbackRelation.MUST_LINK
        else models.FeedbackReason.EXPLICIT_AUTHORITATIVE_CONFLICT
    )
    return graph.create_explicit_edge(
        relation=relation,
        reason=reason,
        source=source,
        target=target,
        provenance=_provenance(source, target),
    )


def test_symmetric_edges_normalize_order_and_require_explicit_authority() -> None:
    left = _record("left")
    right = _record("right")
    edge = _edge(models.FeedbackRelation.MUST_LINK, right, left)
    assert edge.source.pattern_id < edge.target.pattern_id
    with pytest.raises(models.PatternRegistryError) as error:
        graph.create_explicit_edge(
            relation=models.FeedbackRelation.MUST_LINK,
            reason="rag",  # type: ignore[arg-type]
            source=edge.source,
            target=edge.target,
            provenance=edge.provenance,
        )
    assert error.value.code == "EVIDENCE_SOURCE_INVALID"


def test_graph_is_insertion_order_invariant_and_append_is_idempotent() -> None:
    left = _record("left")
    equal = _record("equal")
    conflict = _record("conflict", target_category="other")
    must = _edge(models.FeedbackRelation.MUST_LINK, left, equal)
    cannot = _edge(models.FeedbackRelation.CANNOT_LINK, left, conflict)
    first = graph.create_feedback_graph(edges=(must, cannot))
    second = graph.create_feedback_graph(edges=(cannot, must))
    assert first == second
    assert graph.append_explicit_edge(
        graph.create_feedback_graph(edges=()), must, records=(left, equal)
    ) == graph.append_explicit_edge(
        graph.append_explicit_edge(
            graph.create_feedback_graph(edges=()), must, records=(left, equal)
        ),
        must,
        records=(left, equal),
    )


def test_logical_edge_identity_conflict_never_overwrites_append_only_evidence() -> None:
    left = _record("left")
    right = _record("right")
    clean = _edge(models.FeedbackRelation.MUST_LINK, left, right)
    source = models.FeedbackEndpoint(left.pattern_id, left.candidate_id, left.expected_outcome)
    target = models.FeedbackEndpoint(right.pattern_id, right.candidate_id, right.expected_outcome)
    assert source.outcome is not None and target.outcome is not None
    with_contradiction = graph.create_explicit_edge(
        relation=models.FeedbackRelation.MUST_LINK,
        reason=models.FeedbackReason.EXPLICIT_AUTHORITATIVE_CONFIRMATION,
        source=source,
        target=target,
        provenance=_provenance(source, target),
        contradiction_ids=(_hash("contradiction"),),
    )
    assert clean.edge_id == with_contradiction.edge_id
    assert clean.fingerprint != with_contradiction.fingerprint
    with pytest.raises(models.PatternRegistryError) as error:
        graph.create_feedback_graph(edges=(clean, with_contradiction))
    assert error.value.code == "EDGE_IDENTITY_CONFLICT"


def test_full_pattern_scope_outcome_and_self_edge_validation() -> None:
    source = _record("source")
    target = _record("target", target_category="other")
    edge = _edge(models.FeedbackRelation.CANNOT_LINK, source, target)
    graph.validate_explicit_edge(edge, records=(source, target))

    different_scope = _record(
        "different-scope", target_category="other", scope_category="other-scope"
    )
    scope_edge = _edge(models.FeedbackRelation.CANNOT_LINK, source, different_scope)
    with pytest.raises(models.PatternRegistryError) as error:
        graph.validate_explicit_edge(scope_edge, records=(source, different_scope))
    assert error.value.code == "PATTERN_EVIDENCE_INVALID"

    mismatched_scope = _record("mismatch")
    with pytest.raises(models.PatternRegistryError) as error:
        graph.validate_explicit_edge(edge, records=(mismatched_scope, target))
    assert error.value.code == "PATTERN_EVIDENCE_INVALID"
    endpoint = models.FeedbackEndpoint(
        source.pattern_id, source.candidate_id, source.expected_outcome
    )
    assert endpoint.outcome is not None
    with pytest.raises(models.PatternRegistryError) as error:
        graph.create_explicit_edge(
            relation=models.FeedbackRelation.HARD_NEGATIVE,
            reason=models.FeedbackReason.EXPLICIT_AUTHORITATIVE_CONFLICT,
            source=endpoint,
            target=endpoint,
            provenance=_provenance(endpoint, endpoint),
        )
    assert error.value.code == "SELF_EDGE_INVALID"


def test_must_vs_cannot_and_hard_negative_derive_append_only_contradictions() -> None:
    left = _record("left")
    equal = _record("equal")
    equal_outcome = offline.OutcomeSignature("accept", "quantity_cost", "target")
    conflicting_outcome = offline.OutcomeSignature("accept", "quantity_cost", "other")
    left_equal = models.FeedbackEndpoint(left.pattern_id, left.candidate_id, equal_outcome)
    right_equal = models.FeedbackEndpoint(equal.pattern_id, equal.candidate_id, equal_outcome)
    right_conflict = models.FeedbackEndpoint(
        equal.pattern_id, equal.candidate_id, conflicting_outcome
    )
    must = graph.create_explicit_edge(
        relation=models.FeedbackRelation.MUST_LINK,
        reason=models.FeedbackReason.EXPLICIT_AUTHORITATIVE_CONFIRMATION,
        source=left_equal,
        target=right_equal,
        provenance=_provenance(left_equal, right_equal),
    )
    cannot = graph.create_explicit_edge(
        relation=models.FeedbackRelation.CANNOT_LINK,
        reason=models.FeedbackReason.EXPLICIT_AUTHORITATIVE_CONFLICT,
        source=left_equal,
        target=right_conflict,
        provenance=_provenance(left_equal, right_conflict),
    )
    hard_negative = graph.create_explicit_edge(
        relation=models.FeedbackRelation.HARD_NEGATIVE,
        reason=models.FeedbackReason.EXPLICIT_AUTHORITATIVE_CONFLICT,
        source=left_equal,
        target=right_conflict,
        provenance=_provenance(left_equal, right_conflict),
    )
    contradictions = graph.derive_contradictions(
        graph.create_feedback_graph(edges=(must, cannot, hard_negative))
    )
    for edge in (must, cannot, hard_negative):
        graph.validate_explicit_edge(edge, records=(left, equal))
    assert len(contradictions) == 1
    assert contradictions[0].relation is models.FeedbackRelation.CANNOT_LINK
    assert contradictions[0].evidence_fingerprints == tuple(
        sorted((must.fingerprint, cannot.fingerprint, hard_negative.fingerprint))
    )
    assert left.expected_outcome == equal.expected_outcome


def test_hard_negative_export_is_directional_and_logical_only() -> None:
    source = _record("source")
    target = _record("target", target_category="other")
    hard_negative = _edge(models.FeedbackRelation.HARD_NEGATIVE, source, target)
    exported = graph.export_hard_negative_index(graph.create_feedback_graph(edges=(hard_negative,)))
    assert len(exported.entries) == 1
    assert exported.entries[0].source_pattern_id == source.pattern_id
    assert exported.entries[0].target_pattern_id == target.pattern_id
    assert not set(models.HardNegativeIndex.__dataclass_fields__) & {
        "vector",
        "score",
        "collection",
        "alias",
        "endpoint",
        "tenant",
        "raw_term",
    }


def test_graph_imports_are_pure_and_never_touch_runtime_boundaries() -> None:
    source = graph.__file__
    assert source is not None
    module = ast.parse(Path(source).read_text(encoding="utf-8"))
    imported = {
        name.name.split(".")[0]
        for node in ast.walk(module)
        if isinstance(node, ast.Import)
        for name in node.names
    } | {
        node.module.split(".")[0]
        for node in ast.walk(module)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    for forbidden in ("sqlite", "qdrant", "requests", "http", "admin_panel", "grouping"):
        assert forbidden not in imported


def test_authoritative_observed_outcome_may_differ_from_pattern_expectation() -> None:
    left = _record("observed-left")
    right = _record("observed-right")
    source = models.FeedbackEndpoint(left.pattern_id, left.candidate_id, left.expected_outcome)
    assert source.outcome is not None
    observed = models.FeedbackEndpoint(
        right.pattern_id,
        right.candidate_id,
        offline.OutcomeSignature("accept", "quantity_cost", "observed-category"),
    )
    edge = graph.create_explicit_edge(
        relation=models.FeedbackRelation.CANNOT_LINK,
        reason=models.FeedbackReason.EXPLICIT_AUTHORITATIVE_CONFLICT,
        source=source,
        target=observed,
        provenance=_provenance(source, observed),
    )
    graph.validate_explicit_edge(edge, records=(left, right))
