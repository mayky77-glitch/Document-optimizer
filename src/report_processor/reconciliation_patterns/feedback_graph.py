"""Pure deterministic Wave 4 graph of explicit authoritative feedback only."""

from __future__ import annotations

from dataclasses import dataclass

from .offline import fingerprint
from .pattern_models import (
    FEEDBACK_GRAPH_VERSION,
    FeedbackDirection,
    FeedbackEdge,
    FeedbackEndpoint,
    FeedbackProvenance,
    FeedbackReason,
    FeedbackRelation,
    HardNegativeIndex,
    HardNegativeIndexEntry,
    PatternContradiction,
    PatternRecord,
    PatternRegistryError,
    create_feedback_edge,
    create_hard_negative_index,
)


def _error(code: str, message: str) -> None:
    raise PatternRegistryError(code, message)


def _edge_sort_key(edge: FeedbackEdge) -> tuple[str, str]:
    return edge.edge_id, edge.fingerprint


def feedback_graph_fingerprint(value: object) -> str:
    if isinstance(value, FeedbackGraph):
        return fingerprint({"version": value.version, "edges": value.edges})
    return fingerprint(value)


@dataclass(frozen=True, slots=True)
class FeedbackGraph:
    """Append-only edge set; deterministic order makes identity insertion-order invariant."""

    edges: tuple[FeedbackEdge, ...]
    fingerprint: str
    version: str = FEEDBACK_GRAPH_VERSION

    def __post_init__(self) -> None:
        if self.version != FEEDBACK_GRAPH_VERSION:
            _error("UNSUPPORTED_VERSION", "feedback graph version is unsupported")
        if not isinstance(self.edges, tuple) or any(
            not isinstance(edge, FeedbackEdge) for edge in self.edges
        ):
            _error("EDGE_INVALID", "feedback graph edge is invalid")
        if self.edges != tuple(sorted(self.edges, key=_edge_sort_key)):
            _error("GRAPH_ORDER_INVALID", "feedback graph edges are not canonical")
        if len({edge.edge_id for edge in self.edges}) != len(self.edges):
            _error("EDGE_IDENTITY_CONFLICT", "feedback edge identity conflicts")
        if self.fingerprint != feedback_graph_fingerprint(self):
            _error("FINGERPRINT_MISMATCH", "feedback graph fingerprint does not match")


def create_feedback_graph(*, edges: tuple[FeedbackEdge, ...]) -> FeedbackGraph:
    """Create an insertion-order-invariant graph from typed explicit evidence."""
    if not isinstance(edges, tuple) or any(not isinstance(edge, FeedbackEdge) for edge in edges):
        _error("EDGE_INVALID", "feedback graph edge is invalid")
    ordered = tuple(sorted(edges, key=_edge_sort_key))
    by_id: dict[str, FeedbackEdge] = {}
    for edge in ordered:
        previous = by_id.get(edge.edge_id)
        if previous is not None and previous.fingerprint != edge.fingerprint:
            _error("EDGE_IDENTITY_CONFLICT", "feedback edge identity conflicts")
        by_id[edge.edge_id] = edge
    unique = tuple(by_id[edge_id] for edge_id in sorted(by_id))
    return FeedbackGraph(
        unique, feedback_graph_fingerprint({"version": FEEDBACK_GRAPH_VERSION, "edges": unique})
    )


def create_explicit_edge(
    *,
    relation: FeedbackRelation,
    reason: FeedbackReason,
    source: FeedbackEndpoint,
    target: FeedbackEndpoint,
    provenance: FeedbackProvenance,
    contradiction_ids: tuple[str, ...] = (),
) -> FeedbackEdge:
    """Construct one typed edge, canonicalizing symmetric endpoint order."""
    if reason not in {
        FeedbackReason.EXPLICIT_AUTHORITATIVE_CONFIRMATION,
        FeedbackReason.EXPLICIT_AUTHORITATIVE_CONFLICT,
    }:
        _error("EVIDENCE_SOURCE_INVALID", "feedback evidence is not authoritative")
    if not isinstance(relation, FeedbackRelation):
        _error("EDGE_INVALID", "feedback graph edge is invalid")
    if not isinstance(source, FeedbackEndpoint) or not isinstance(target, FeedbackEndpoint):
        _error("EDGE_INVALID", "feedback graph edge is invalid")
    if source.pattern_id == target.pattern_id:
        _error("SELF_EDGE_INVALID", "feedback edge cannot be self-referential")
    direction = (
        FeedbackDirection.DIRECTIONAL
        if relation is FeedbackRelation.HARD_NEGATIVE
        else FeedbackDirection.SYMMETRIC
    )
    if direction is FeedbackDirection.SYMMETRIC and source.pattern_id > target.pattern_id:
        source, target = target, source
    return create_feedback_edge(
        relation=relation,
        direction=direction,
        reason=reason,
        source=source,
        target=target,
        provenance=provenance,
        contradiction_ids=contradiction_ids,
    )


def validate_explicit_edge(edge: FeedbackEdge, *, records: tuple[PatternRecord, ...]) -> None:
    """Bind typed feedback evidence to known candidate identities, scope, and outcomes."""
    if not isinstance(edge, FeedbackEdge):
        _error("EDGE_INVALID", "feedback graph edge is invalid")
    if edge.reason not in {
        FeedbackReason.EXPLICIT_AUTHORITATIVE_CONFIRMATION,
        FeedbackReason.EXPLICIT_AUTHORITATIVE_CONFLICT,
    }:
        _error("EVIDENCE_SOURCE_INVALID", "feedback evidence is not authoritative")
    if not isinstance(records, tuple) or any(
        not isinstance(item, PatternRecord) for item in records
    ):
        _error("PATTERN_EVIDENCE_INVALID", "pattern evidence is invalid")
    by_id = {record.pattern_id: record for record in records}
    if len(by_id) != len(records):
        _error("PATTERN_EVIDENCE_INVALID", "pattern evidence is invalid")
    source = by_id.get(edge.source.pattern_id)
    target = by_id.get(edge.target.pattern_id)
    if (
        source is None
        or target is None
        or source.candidate_id != edge.source.candidate_id
        or target.candidate_id != edge.target.candidate_id
        or source.scope != target.scope
    ):
        _error("PATTERN_EVIDENCE_INVALID", "feedback evidence does not match full pattern scope")


def append_explicit_edge(
    graph: FeedbackGraph, edge: FeedbackEdge, *, records: tuple[PatternRecord, ...]
) -> FeedbackGraph:
    """Validate and append one authoritative edge; exact repeats are idempotent."""
    if not isinstance(graph, FeedbackGraph):
        _error("GRAPH_INVALID", "feedback graph is invalid")
    validate_explicit_edge(edge, records=records)
    for existing in graph.edges:
        if existing.edge_id == edge.edge_id:
            if existing.fingerprint == edge.fingerprint:
                return graph
            _error("EDGE_IDENTITY_CONFLICT", "feedback edge identity conflicts")
    return create_feedback_graph(edges=(*graph.edges, edge))


def _pair(edge: FeedbackEdge) -> tuple[str, str]:
    return tuple(sorted((edge.source.pattern_id, edge.target.pattern_id)))  # type: ignore[return-value]


def derive_contradictions(graph: FeedbackGraph) -> tuple[PatternContradiction, ...]:
    """Derive append-only must-vs-negative contradictions without latest-wins semantics."""
    if not isinstance(graph, FeedbackGraph):
        _error("GRAPH_INVALID", "feedback graph is invalid")
    grouped: dict[tuple[str, str], list[FeedbackEdge]] = {}
    for edge in graph.edges:
        grouped.setdefault(_pair(edge), []).append(edge)
    derived: list[PatternContradiction] = []
    for (left, right), edges in grouped.items():
        relations = {edge.relation for edge in edges}
        if FeedbackRelation.MUST_LINK not in relations or not relations & {
            FeedbackRelation.CANNOT_LINK,
            FeedbackRelation.HARD_NEGATIVE,
        }:
            continue
        evidence = tuple(sorted(edge.fingerprint for edge in edges))
        contradiction_id = fingerprint(
            {
                "relation": FeedbackRelation.CANNOT_LINK.value,
                "left_pattern_id": left,
                "right_pattern_id": right,
                "evidence_fingerprints": evidence,
            }
        )
        derived.append(
            PatternContradiction(
                contradiction_id,
                FeedbackRelation.CANNOT_LINK,
                left,
                right,
                evidence,
            )
        )
    return tuple(sorted(derived, key=lambda item: item.contradiction_id))


def export_hard_negative_index(graph: FeedbackGraph) -> HardNegativeIndex:
    """Export only directional opaque logical metadata, never vector or term material."""
    if not isinstance(graph, FeedbackGraph):
        _error("GRAPH_INVALID", "feedback graph is invalid")
    entries = tuple(
        sorted(
            (
                HardNegativeIndexEntry(
                    edge.source.pattern_id,
                    edge.target.pattern_id,
                    edge.fingerprint,
                )
                for edge in graph.edges
                if edge.relation is FeedbackRelation.HARD_NEGATIVE
            ),
            key=lambda item: (
                item.source_pattern_id,
                item.target_pattern_id,
                item.edge_fingerprint,
            ),
        )
    )
    return create_hard_negative_index(entries=entries)
