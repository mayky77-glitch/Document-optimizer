---
type: task
status: blocked
work_id: reconciliation-wave6-core-v1
role: worker
agent_role: developer
owner: "wave6-core"
profile: L2
routing_grade: P4
progress_revision: 3
state_fingerprint: ""
no_progress_count: 3
circuit_state: hard_stop
routing_reason: "Deterministic multi-channel ranking and authority boundaries are coupled"
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
  - "src/report_processor/reconciliation_patterns/hybrid_retrieval.py"
source_paths:
  - "knowledge/tasks/reconciliation-wave6-contract.md"
depends_on:
  - "reconciliation-wave6-contract"
tags:
  - "task/implementation"
  - "status/blocked"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 6 hybrid core

Implement only the frozen pure core. No runtime wiring or legacy edits. Leave
in review with changed path, focused tests, assumptions and residual risks.

## Blocked handoff

Three adversarial audit cycles still found callable authority construction,
noncanonical direct batches, hard-negative cross-binding failures and direct
schema-validation bypasses. ORDA circuit is open; the source adapter remains
blocked until a new evidence revision and separately approved remediation.
