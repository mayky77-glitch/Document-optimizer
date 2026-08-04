---
type: task
status: done
work_id: reconciliation-wave4-design-v1
role: auditor
agent_role: architect
owner: "wave4-contract"
profile: L3
routing_grade: P6
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "New lifecycle persistence and feedback precedence contract is consequential architecture"
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-sol
reasoning_effort: high
launch_status: inherited
actual_model: "gpt-5.6-sol"
actual_reasoning_effort: "high"
fallback_reason: "Persistent architect route is pinned to Sol/high; launch result exposes task identity only."
model_fallback: false
last_verified: 2026-08-04
updated: 2026-08-04
write_scope: []
source_paths: []
depends_on:
  - "reconciliation-wave3-acceptance-audit"
tags:
  - "task/audit"
  - "status/draft"
  - "task/design"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 4 frozen registry and feedback contract

## Goal

Freeze Wave 4 lifecycle, immutable record schemas, persistence, precedence,
feedback graph, approval and rollback boundaries before implementation.

## Scope and instructions

- Design read-only; do not edit production or tests.
- Keep activation and replay outside Wave 4; Wave 5 owns promotion gates.
- Preserve exact feedback precedence and prohibit self-training.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: none; architecture was read-only.
- Commands and tests run: CodeGraph/source/test review of Wave 3, exact feedback,
  audit journal, persistence, grouping identities and Qdrant boundary.
- Result: implementation-ready frozen contract below.
- Risks or follow-up: activation identity, trusted exporter, real version values,
  Wave 5 gates, store retention/location and physical Qdrant remain owner decisions.

## Frozen contract

New production files only:

- `pattern_models.py` — shared immutable contracts and fingerprints.
- `pattern_registry.py` — candidate registration, lifecycle, precedence.
- `feedback_graph.py` — explicit-confirmation graph and logical hard negatives.
- `pattern_persistence.py` — private append-only SQLite v1.

New tests only:

- `tests/contract/test_pattern_registry_contract.py`
- `tests/unit/reconciliation_patterns/test_pattern_registry.py`
- `tests/unit/reconciliation_patterns/test_feedback_graph.py`
- `tests/integration/test_pattern_registry_persistence.py`

Forbidden edits: accepted `offline.py`, empty package `__init__.py`, admin panel,
legacy feedback/review/grouping/audit, scripts, XLSX and Qdrant/runtime wiring.

Versions: `PatternRegistry-1.0`, `FeedbackGraph-1.0`,
`PatternRegistryEvent-1.0`, `FeedbackGraphHardNegative-1.0`, store schema `1`.
Reuse accepted Wave 3 candidate/scope/proposal/outcome/support/rational types.

Public models are frozen/slotted and recursively immutable; only sorted unique
tuples/frozensets. No dict/list/set/datetime/float. `PatternRecord` contains
stable candidate `pattern_id`, sequential revision/previous fingerprint, state,
all parser/model/taxonomy versions, scope/template/support, hard negatives,
contradictions, replay/owner/activation/rollback metadata, supersession and risk
codes. Fingerprint covers every field except itself via Wave 3 canonical JSON.

Lifecycle: `proposed -> shadow -> owner_approved`; Wave 4 rejects
`owner_approved -> active` with `WAVE5_REQUIRED`. Active records may only arrive
from a future verified Wave 5 boundary. Conflicts suspend active patterns.
Retired is terminal. Suspended never reactivates in Wave 4. Supersession retires
old and creates a different-ID proposed pattern atomically. Rollback appends a
suspended revision and never mutates/reactivates history.

Feedback graph edges require two explicit authoritative confirmation records
with opaque refs, independent document-set refs and apply/result fingerprints.
RAG, dense score, machine suggestion, autosave, audit feedback and unresolved
rows are invalid evidence. Must-link is symmetric/equal-outcome; cannot-link is
symmetric/controlled conflict; hard-negative is directional. Conflicting edges
remain append-only and derive a contradiction.

Decision precedence is exact feedback first. Otherwise only current-version
active patterns can decide; no match or conflicting outcomes returns manual.
Shadow/approved/suspended/retired/RAG never decide. Wave 4 therefore cannot
change current authoritative results.

SQLite uses explicit caller path, private mode 0600, schema/user_version 1,
foreign keys, trusted schema off, synchronous full, `BEGIN IMMEDIATE`, immutable
record/event/edge tables and UPDATE/DELETE-blocking triggers. Reads verify
canonical payloads, fingerprints, revision/event chains and graph identity.
Stale heads fail. Supersession/conflict suspension/rollback commit atomically.
No import/migration from legacy feedback, autosave or Block 16 audit.

Hard-negative index output is logical opaque metadata only: no vector, score,
collection, alias, endpoint, tenant or raw term. No network/Qdrant imports.

Wave 5 exclusively owns replay contents, thresholds, holdout, equivalence,
activation and reactivation. Production remains STOP.

## Handoff

Leave this card in `review` until orchestration accepts the result.
