---
type: task
status: superseded
work_id: reconciliation-wave4-models-v1
role: worker
agent_role: developer
owner: "wave4-models-core"
profile: L2
routing_grade: P4
progress_revision: 1
state_fingerprint: "sha256:db40b82f7f7a7acb5f5f6fd0d02e944ee12606d6ecf9549640d82b094ab56919"
no_progress_count: 0
circuit_state: closed
routing_reason: "Dense immutable cross-module contract and canonical identity require difficult implementation"
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
  - "reconciliation-wave4-contract"
tags:
  - "task/implementation"
  - "status/draft"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 4 immutable pattern models

## Goal

Implement the frozen Wave 4 immutable public models, validation and canonical
fingerprint material in one isolated module.

## Scope and instructions

- Modify only `write_scope` paths.
- Reuse accepted Wave 3 public types and canonical JSON helpers unchanged.
- Reject malformed hashes, versions, tuple order, floats and inconsistent state metadata.
- Include lifecycle, feedback graph, event, hard-negative index and integrity-report models.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: `src/report_processor/reconciliation_patterns/pattern_models.py`
  and this task card only.
- Commands and tests run: `.venv/bin/ruff format --check` and
  `.venv/bin/ruff check` for the new module; a create/canonical JSON/load
  model smoke check; `28 passed` for the Wave 4 model contract plus the
  accepted Wave 3 offline regression slice.
- Result: frozen/slotted immutable registry, feedback, event, hard-negative
  and integrity contracts now validate version/hash/order/privacy/state and
  revision-chain invariants. Canonical fingerprint constructors/loaders are
  available. Activation transition is rejected with `WAVE5_REQUIRED`.
- Risks or follow-up: registry, feedback and SQLite modules must preserve these
  public constructors/loaders and supply authoritative confirmation provenance;
  they remain responsible for append-only sequencing and atomic lifecycle work.

## Handoff

Leave this card in `review` until orchestration accepts the result.
