---
type: task
status: superseded
work_id: reconciliation-wave4-models-remediation-v1
role: worker
agent_role: developer
owner: "wave4-models-remediation-core"
profile: L2
routing_grade: P4
progress_revision: 1
state_fingerprint: "sha256:4899067fe1cea8f3ab450f13061f9fac2060556fb826e927b20a14ce7596c0d3"
no_progress_count: 0
circuit_state: closed
routing_reason: "P6 found critical lifecycle candidate identity and graph semantic defects"
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: confirmed
actual_model: "gpt-5.6-terra"
actual_reasoning_effort: "high"
fallback_reason: ""
model_fallback: false
last_verified: 2026-08-04
updated: 2026-08-04
write_scope:
  - "src/report_processor/reconciliation_patterns/pattern_models.py"
source_paths:
  - "src/report_processor/reconciliation_patterns/pattern_models.py"
depends_on:
  - "reconciliation-wave4-models-audit"
tags:
  - "task/implementation"
  - "status/draft"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 4 model audit remediation

## Goal

Close all four accepted P6 model findings before dependent Wave 4 streams.

## Scope and instructions

- Modify only `write_scope` paths.
- Fix type-specific approval/activation/rollback revision and lifecycle retention.
- Preserve and revalidate the full accepted Wave 3 candidate identity/evidence semantics.
- Bind typed endpoints, direction, reason and explicit authoritative provenance to edges.
- Normalize all malformed constructor/loader inputs to PatternRegistryError.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: `src/report_processor/reconciliation_patterns/pattern_models.py`
  and this remediation card only.
- Commands and tests run: CodeGraph sync/explore; `.venv/bin/ruff format
  --check` and `.venv/bin/ruff check`; expanded Wave 4 remediation contract
  plus Wave 3 profile/mine/evaluate/offline regression (`49 passed`); focused
  create/canonical/load lifecycle, candidate, feedback and hard-negative smoke.
- Result: all four accepted P6 groups are closed. Lifecycle metadata uses
  type-specific revisions, imported active records require opaque Wave 5
  verification, Wave 4 activation still fails `WAVE5_REQUIRED`, and active
  suspension/retirement retains provenance. Full Wave 3 candidate identity and
  evidence are recomputed. Typed feedback edges enforce direction, controlled
  reason, two independent authoritative confirmations and relation outcomes.
  Malformed public mappings fail with `PatternRegistryError`.
- Risks or follow-up: append-only stores remain responsible for verifying
  cross-record previous fingerprints and atomic transition/event transactions;
  these immutable models validate each record and its retained metadata.

## Handoff

Leave this card in `review` until orchestration accepts the result.
