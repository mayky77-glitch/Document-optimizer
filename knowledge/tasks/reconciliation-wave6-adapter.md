---
type: task
status: done
work_id: reconciliation-wave6-adapter-v1
role: worker
agent_role: developer
owner: "wave6-adapter"
profile: L2
routing_grade: P4
progress_revision: 1
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Adapter must bind existing dense/registry sources without widening authority"
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
  - "src/report_processor/reconciliation_patterns/hybrid_sources.py"
  - "tests/integration/test_hybrid_retrieval_sources.py"
source_paths:
  - "knowledge/tasks/reconciliation-wave6-contract.md"
depends_on:
  - "reconciliation-wave6b-acceptance-audit-v1"
tags:
  - "task/integration"
  - "status/done"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 6 source adapter

Accepted after red-first ORDA recovery. The adapter binds existing dense store,
registry precedence, semantic skeleton and hard-negative export without editing
those modules or widening authority.

## Result

- `HybridSources.collect(...)` emits the six canonical positive batches and one
  hard-negative batch for `rank_hybrid(...)`.
- Authoritative exact/ACTIVE decisions short-circuit every source call.
- Confirmed, prototype and negative source identities remain isolated.
- Dense evidence is rejected on missing review attestation, taxonomy, category,
  tenant/project, scope, consequential version or embedding mismatch.
- Source failures fail closed per channel; raw terms/vectors/backend errors do
  not enter DTOs, fingerprints or logs.
- Adapter is inert: no runtime wiring, persistence or automatic decision path.

## Acceptance

- adapter integration: `16 passed`;
- adapter plus core: `32 passed`;
- relevant reconciliation set: `129 passed`;
- scoped Ruff, format, `py_compile` and `git diff --check`: passed;
- independent P6 audit: `ACCEPT`, no findings.
