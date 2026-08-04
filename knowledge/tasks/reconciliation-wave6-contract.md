---
type: task
status: done
work_id: reconciliation-wave6-gate0-v1
role: worker
agent_role: orchestrator
owner: "wave6-gate0"
profile: L3
routing_grade: P5
progress_revision: 1
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Cross-component retrieval contract requires dependency and authority-boundary synthesis"
assigned_model: gpt-5.6-sol
reasoning_effort: medium
launch_status: confirmed
actual_model: "gpt-5.6-sol"
actual_reasoning_effort: "medium"
fallback_reason: ""
model_fallback: false
last_verified: 2026-08-04
updated: 2026-08-04
write_scope: []
source_paths: []
depends_on:
  - "reconciliation-wave5-final-acceptance-audit"
tags:
  - "task/contract"
  - "status/done"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 6 hybrid retrieval contract

## Goal

Freeze an inert deterministic `HybridRetrieval-1.0` bridge. It combines
authoritative precedence, lexical/pattern/dense/prototype signals and separate
hard-negative evidence without changing any authoritative decision.

## Frozen scope

- Core: `src/report_processor/reconciliation_patterns/hybrid_retrieval.py`.
- Core tests: `tests/contract/test_hybrid_retrieval_contract.py` and
  `tests/unit/reconciliation_patterns/test_hybrid_retrieval.py`.
- Adapter after core acceptance:
  `src/report_processor/reconciliation_patterns/hybrid_sources.py` and
  `tests/integration/test_hybrid_retrieval_sources.py`.
- Forbidden: edits to existing `stage_rag`, registry, feedback graph, replay,
  persistence, drawing-card/admin, `__init__.py`, scripts, dependencies and
  spreadsheets.

## Public core boundary

Version `HYBRID_RETRIEVAL_VERSION = "HybridRetrieval-1.0"`; offline defaults
`RRF_K = 60`, `SCORE_SCALE = 1_000_000`.

Enums:

- `HybridStatus`: `authoritative_exact`, `authoritative_pattern`,
  `review_required`, `unavailable`.
- `EvidenceKind`: `confirmed_example`, `active_pattern_prototype`.
- `RepresentationKind`: `full_term`, `semantic_skeleton`.
- `RetrievalChannel`: `pattern_mask`, `lexical`, `dense_full_term`,
  `dense_semantic_skeleton`, `prototype_full_term`,
  `prototype_semantic_skeleton`.
- `ReasonCode`: controlled exact/pattern, conflict, channel, slot,
  hard-negative, exact-only, unavailable and manual-review reasons.

Exact frozen/slotted immutable models after P6/security recovery:

- `HybridQuery(query_ref, tenant_ref, project_ref, document_type_fingerprint,
  taxonomy_version_fingerprint, scope_fingerprint,
  consequential_version_fingerprint, embedding_identity_fingerprint,
  confirmed_source_identity_fingerprint,
  prototype_source_identity_fingerprint,
  hard_negative_identity_fingerprint, full_term_fingerprint,
  skeleton_fingerprint, exact_only, limit, fingerprint, version)`.
- `AuthorityEnvelope(query_fingerprint, decision, exact_feedback_ref,
  active_pattern_ids, active_head_fingerprints,
  consequential_version_fingerprint, fingerprint, version)`. Exact feedback
  requires one feedback ref and no pattern IDs; ACTIVE requires nonempty exact
  ID/head tuples equal to the decision IDs; manual conflict binds the same
  current head set. Its constructor is not public: `resolve_authority(...)`
  derives it from `RegistryHistory`, current `PatternVersions` and exact-feedback
  attestation using `resolve_history_precedence`. Bare `PatternDecision` is
  never accepted by the core.
- `HybridEvidence(evidence_ref, semantic_identity_fingerprint, kind,
  pattern_id, outcome, tenant_ref, project_ref, document_type_fingerprint,
  taxonomy_version_fingerprint, scope_fingerprint,
  consequential_version_fingerprint, embedding_identity_fingerprint,
  full_term_fingerprint, confirmed, unit_compatible,
  critical_slots_compatible, replay_fingerprint, owner_approval_ref,
  activation_fingerprint, contradiction_count, supporting_refs,
  matched_slot_kinds, difference_codes, fingerprint, version)`. Confirmed
  examples have no lifecycle refs. Prototypes require a pattern ID, replay,
  owner approval, activation and zero contradictions.
- `RankedSignal(channel, representation, evidence_ref, rank,
  similarity_micros, index_identity_fingerprint, fingerprint, version)`.
- `SignalBatch(query_fingerprint, channel, signals, unavailable,
  source_identity_fingerprint, fingerprint, version)`.
- `HardNegativeHit(query_fingerprint, positive_identity_fingerprint, negative_ref,
  source_pattern_id, target_pattern_id, edge_fingerprint, representation,
  rank, similarity_micros, direct_cannot_link, scope_fingerprint,
  consequential_version_fingerprint, difference_codes, fingerprint, version)`.
- `HardNegativeBatch(query_fingerprint, hits, unavailable,
  source_identity_fingerprint, fingerprint, version)`.
- `RationalScore(numerator, denominator)` reduced and nonnegative.
- `HybridExplanation(reason_codes, positive_refs, hard_negative_refs,
  matched_slot_kinds, difference_codes, fingerprint, version)`.
- `RankedHybridCandidate(semantic_identity_fingerprint, evidence_refs,
  outcome, score, channel_count, rank, explanation, fingerprint, version)`.
- `HybridRetrievalResult(query_fingerprint, status, authority, candidates,
  hard_negatives, unavailable_channels,
  requires_manual_review, auto_accepted, fingerprint, version)`.

`resolve_authority(query, *, exact_feedback, exact_feedback_ref,
matched_histories, current_versions, feedback_pattern_id)` is the sole authority
builder. `rank_hybrid(query, *, authority, evidence, batches,
hard_negative_batch)` is pure.
Adapter collection is separate and transient; raw normalized term/skeleton may
enter an adapter but never a public model, result, fingerprint error or log.

## Authority and ranking

- A query-bound `AuthorityEnvelope` built from accepted history precedence runs
  first. Exact feedback and one
  current conflict-free ACTIVE pattern short-circuit before any source call.
  Conflicting patterns require manual review.
- `auto_accepted` is always `False` in this inert bridge. Exact/ACTIVE status
  only short-circuits hybrid collection; existing registry precedence remains
  the authoritative decision owner. Hybrid candidates always remain
  assistive/manual and never become feedback or training data.
- Six positive channels use equal-weight exact RRF:
  `sum(1 / (60 + channel_rank))`. Keep exact reduced rational arithmetic.
- Per `(semantic identity, channel)`, only best rank counts. Duplicate examples
  and prototype points cannot amplify one channel.
- Sort by score descending, distinct channel count descending, semantic identity
  fingerprint ascending. Candidate ranks are contiguous. Input order cannot
  change output or fingerprints.
- `similarity_micros` is integer `0..1_000_000`, explanation/margin only, and is
  never summed across channels.
- Exactly one explicit batch exists for every channel. Signals are sorted and
  unique with contiguous ranks `1..n`; signal index identity equals its batch.
  Channel, representation and evidence kind follow a frozen compatibility
  matrix. Any violation makes the whole batch unavailable.
- Confirmed-example and prototype source identities are distinct, query-bound
  fields. Pattern/prototype channels use only the prototype identity;
  lexical/dense-example channels use only the confirmed identity. Negative
  identity differs from both. Signal index equals its batch and expected source.

## Filters and hard negatives

- Before ranking, evidence attestation proves: exact tenant; optional project;
  document/taxonomy;
  embedding model/revision/dimension identity; confirmed/ACTIVE status; current
  consequential version; exact scope boundary; critical-slot compatibility;
  compatible unit; direct contradictions/cannot-link.
- Unknown unit or `exact_only` permits only evidence whose bound full-term
  fingerprint equals the query full-term fingerprint.
- Any context mismatch makes the whole source batch unavailable; never leak a
  partially filtered batch.
- Hard negatives arrive in one required query/context/index-bound batch and
  never enter positive RRF. Missing/unavailable/mismatched negative source emits
  no candidates. `direct_cannot_link` is adapter-attested in the candidate-to-
  negative direction and excludes the candidate, including confirmed evidence
  without a pattern ID. Reverse edges do not. Margin compares only within the
  same representation; similarity greater than or equal to positive adds a
  manual blocker.
- Full-term and skeleton vectors remain separate. Pattern prototypes use a
  separate index and only current-version ACTIVE records with replay, owner,
  activation and zero contradictions. V1 uses deterministic prototype text and
  skeleton; no centroids or Cross-Encoder.

## Privacy and failures

Every public ref/pattern ID is `sha256:<64 lowercase hex>`. Slot/difference and
outcome fields use a strict controlled-token allowlist; mode is only
`quantity_cost`/`cost_only`. Public values contain only controlled enums/codes,
integers, booleans, salted refs, fingerprints and controlled outcomes. Forbidden: raw terms,
skeleton text, slot values, vectors, filenames, paths, URIs, tenant/backend
names and backend exception strings. Collections are sorted tuples. Fingerprints
are canonical and self-validating. Direct result construction revalidates
authority/status/order/uniqueness invariants. Stable privacy-safe schema/version/
fingerprint/context/ranking/source codes fail closed.

Bounds before fingerprint/ranking: `limit <= 100`; evidence and negative hits
`<= 4096`; signals per channel `<= 1000`; supporting refs `<= 128`; controlled
code tuples `<= 64`. Grouping is linear/list-based, not tuple concatenation.

## Acceptance and owner gates

Exact fields/enums/import surface; fingerprint tamper and raw path/URI rejection;
authority-envelope forgery/state tests; golden RRF fractions;
permutation/tie/dedupe; every filter; source-not-called precedence; directed
and reverse-edge hard negatives; same-representation margin; exact-only positive
and negative cases; channel/representation/kind matrix; complete positive and
negative source batches; two-representation/prototype isolation; unavailable fallback;
privacy scan; no automatic dense decision; unchanged legacy suites.

Final recovery also requires action-dependent controlled outcomes (`reject`
uses `None/None`); model tuples validate element types before sorting; batch
input order cannot change output; margin uses the best positive within the same
representation; candidate/explanation/result negative refs are cross-bound;
bool-as-int and authoritative source artifacts are rejected.

Offline implementation may use provisional active-only prototypes and RRF
`k=60`. Production remains STOP until owners approve them plus index retention,
aliases, top-k, latency, Recall/MRR/top-1 and review-rate thresholds. Centroids,
weights and Cross-Encoder require a new version and holdout.
