---
type: task
status: blocked
work_id: reconciliation-wave6-core-v1
role: worker
agent_role: tester
owner: "wave6-tests"
profile: L1
routing_grade: P3
progress_revision: 3
state_fingerprint: ""
no_progress_count: 3
circuit_state: hard_stop
routing_reason: "Frozen schema and deterministic ranking need an independent executable contract"
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: confirmed
actual_model: "gpt-5.6-terra"
actual_reasoning_effort: "medium"
fallback_reason: ""
model_fallback: false
last_verified: 2026-08-04
updated: 2026-08-04
write_scope:
  - "tests/contract/test_hybrid_retrieval_contract.py"
  - "tests/unit/reconciliation_patterns/test_hybrid_retrieval.py"
source_paths:
  - "knowledge/tasks/reconciliation-wave6-contract.md"
depends_on:
  - "reconciliation-wave6-contract"
tags:
  - "task/tests"
  - "status/blocked"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 6 hybrid core tests

Freeze every field, invariant, authority short-circuit, RRF/tie/dedupe rule,
hard-negative gate, privacy rule and malformed-input failure. No production edits.

## Blocked handoff

The focused suite passes but does not cover the final P6 counterexamples listed
in `reconciliation-wave6-final-audit`. It cannot be accepted as the contract
suite until those direct-construction and multi-negative cases are executable.
