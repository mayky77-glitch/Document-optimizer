---
type: task
status: done
work_id: reconciliation-wave5-contract-exploration-v1
role: auditor
agent_role: architect
owner: "wave5-contract"
profile: L3
routing_grade: P6
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Replay gates and activation boundary can change authoritative outcomes"
assigned_model: gpt-5.6-sol
reasoning_effort: high
launch_status: confirmed
actual_model: "gpt-5.6-sol"
actual_reasoning_effort: "high"
fallback_reason: ""
model_fallback: false
last_verified: 2026-08-04
updated: 2026-08-04
write_scope: []
source_paths: []
depends_on:
  - "reconciliation-wave4-final-acceptance"
tags:
  - "task/contract"
  - "status/done"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 5 offline replay and promotion contract

## Goal

Freeze replay inputs, immutable outputs, metrics, holdout separation,
equivalence gates, activation/reactivation ownership and Wave 4 import boundary.

## Completion evidence

- Changed paths: this card only after root synthesis.
- Result: frozen contract below.
- Risks or follow-up: activation remains STOP until representative sealed
  baseline/holdout and explicit owner-approved policy exist.

## Frozen scope

- Production: `src/report_processor/reconciliation_patterns/replay.py`.
- Tests: `tests/contract/test_grouping_replay_contract.py`,
  `tests/unit/reconciliation_patterns/test_replay.py`,
  `tests/integration/test_grouping_replay_oracles.py`.
- Versions: `GroupingReplay-1.0`, `GroupingPromotionPolicy-1.0`.
- No edits or wiring to Wave 3/4, `__init__.py`, persistence, admin, legacy
  grouping/calculation/writer, scripts, dependencies or spreadsheet fixtures.

## Public boundary

`run_grouping_replay(...)` accepts one exact PatternRecord, sealed baseline and
holdout snapshot identities, explicit fingerprinted PromotionPolicy, injected
executor/calculation/XLSX oracles, monotonic clock and index measurement. Pure
helpers evaluate shadow/promotion, derive owner-approval ref and build
ActivationMetadata. Replay never persists, writes XLSX or activates directly.

Public models are frozen/slotted and recursively immutable: ReplaySplit,
PromotionVerdict, MeasurementStatus, Ratio, ReplaySnapshotIdentity,
ReplayObservation, SplitReplayMetrics, IndexMeasurement, ReplayMeasurements,
PromotionPolicy, GroupingReplayReport, PromotionDecision and OracleResult.
Collections are sorted tuples; numbers are int/Decimal, never float/datetime.
Opaque refs and fingerprints are `sha256:<64 lowercase hex>`.

Exact public field matrix:

- `Ratio(numerator, denominator)`.
- `OracleResult(case_count, mismatch_refs, oracle_fingerprint, version)`.
- `ReplaySnapshotIdentity(split, snapshot_ref, manifest_fingerprint,
  corpus_fingerprint, source_set_refs, document_set_refs,
  consequential_version_fingerprint, row_count, review_row_count,
  review_group_count, sealed, seal_ref, fingerprint, version)`.
- `ReplayObservation(snapshot_fingerprint, evaluated_head_fingerprint,
  effective_decision_fingerprint, pattern_decision_refs,
  correct_decision_refs, covered_row_refs, covered_group_refs,
  supporting_document_set_refs, contradiction_refs, forbidden_pair_refs,
  category_change_refs, mode_change_refs, unit_change_refs,
  decision_mismatch_refs, manual_group_count, manual_action_count,
  unresolved_row_count, double_membership_count, calculation_oracle,
  xlsx_oracle, semantic_fingerprint, version)`.
- `SplitReplayMetrics(split, snapshot_fingerprint, coverage_rows,
  coverage_groups, precision, support_document_set_count,
  contradiction_count, forbidden_merge_count, manual_group_before,
  manual_group_after, manual_action_before, manual_action_after,
  unresolved_before, unresolved_after, changed_category_count,
  changed_mode_count, changed_unit_count, decision_mismatch_count,
  double_membership_count, calculation_mismatch_count,
  xlsx_mismatch_count, before_semantic_fingerprint,
  after_semantic_fingerprint, repeat_semantic_fingerprint, fingerprint,
  version)`.
- `IndexMeasurement(status, environment_ref, index_ref, size_bytes,
  fingerprint, version)`.
- `ReplayMeasurements(latency_samples_ns, p50_latency_ns, p95_latency_ns,
  index, fingerprint, version)`.
- `PromotionPolicy(policy_ref, owner_ref, approval_ref, release_window_ref,
  allowed_kinds, allowed_scope_fingerprints, min_support_document_sets,
  min_holdout_document_sets, min_holdout_decisions, min_coverage_rows,
  min_coverage_groups, min_precision, max_manual_group_count,
  max_manual_action_count, max_unresolved_row_count, max_p95_latency_ns,
  index_required, max_index_size_bytes, fingerprint, version)`.
- `GroupingReplayReport(evaluated_pattern_id, evaluated_head_fingerprint,
  policy_fingerprint, baseline_snapshot_fingerprint,
  holdout_snapshot_fingerprint, baseline_metrics, holdout_metrics,
  deterministic_repeatability, semantic_fingerprint, measurements,
  fingerprint, version)`.
- `PromotionDecision(verdict, reason_codes, report_fingerprint,
  policy_fingerprint, head_fingerprint, fingerprint, version)`.

## Replay rules

- Snapshots must be sealed, version-compatible and have disjoint source-set and
  independent document-set refs plus distinct manifest/corpus fingerprints.
- Policy is explicit, approved and fingerprinted before holdout execution.
  Missing policy means no holdout run and activation STOP.
- Each split runs once without pattern and twice with exact head. Candidate
  semantic fingerprints must repeat byte-identically. Injected clock supplies
  nonnegative integer nanoseconds only.
- Coverage rows/groups, precision and support use exact integer numerator /
  denominator Ratios. `(0, 0)` is undefined and fails any required gate.
- Counts cover contradictions, forbidden pairs, manual groups/actions,
  unresolved rows, changed category/mode/unit decisions, double membership and
  equivalence mismatches. Unique opaque refs define every count.
- Calculation equivalence compares selected identities/status and every finite
  Decimal quantity/cost/coefficient/category total. XLSX oracle compares current
  target-schema cells/values/formats; no workbook bytes enter report.
- Oracle case count must be positive and all mismatch counts zero.
- Latency percentiles use sorted samples and nearest rank. Semantic fingerprint
  excludes clock/index measurements; full report fingerprint includes them.

## Promotion gates

Shadow only: at least 3 confirmed supports, 2 independent document sets, zero
contradictory support, PatternRecord contradictions and risk codes. Shadow never
changes authoritative decisions.

Activation additionally requires exact current owner-approved successor and
bound approval ref; allowed kind/scope; every owner-configured holdout/support /
coverage/precision/manual/latency/index threshold; zero contradictions,
forbidden merges, decision mismatches, double membership and calculation/XLSX
mismatches; deterministic repeatability. Missing/undefined policy, threshold or
required measurement fails closed. Suspended/retired reactivation is unsupported
in 1.0; use different-ID supersession and fresh replay.

`build_activation_metadata` returns metadata only for `activation_eligible`:
verification ref equals report fingerprint, fingerprint binds current approved
head/report/policy/owner approval/measurements, revision is head+1. Caller may
pass it only to existing `import_verified_wave5_active()`.

## Stable failures and privacy

Malformed execution raises privacy-safe schema/version/fingerprint/snapshot /
overlap/sealing/version/state/executor/nondeterminism/oracle/measurement codes.
Valid STOP decisions carry sorted reason codes for missing policy/approval,
support/holdout/precision/coverage, conflicts/forbidden merges/mismatches,
manual regression, equivalence, latency/index, stale approval and unsupported
reactivation.

Reports contain only versions, counts, ratios, booleans, opaque salted refs and
fingerprints. Forbidden: raw terms, paths/names, sheet/cell/row coordinates,
formulas/comments, quantities/costs, workbook bytes and source digests.
Production `replay.py` cannot import processing/admin/legacy grouping,
calculation/writer/XLSX, RAG/Qdrant, SQLite, network/AI, subprocess or filesystem.

## Owner decisions

Representative sealed corpus/holdout; all promotion thresholds; allowed kinds /
scopes; latency/index applicability and limits; release window; promotion,
rollback, domain, privacy and corpus owners. Until supplied: production STOP.
