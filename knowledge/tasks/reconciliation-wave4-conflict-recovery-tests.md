---
type: task
status: done
work_id: reconciliation-wave4-conflict-recovery-tests-v1
role: worker
agent_role: tester
owner: "wave4-conflict-recovery-tests"
profile: L3
routing_grade: P5
progress_revision: 3
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Close explicit adversarial persistence acceptance matrix"
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: inherited
actual_model: gpt-5.6-terra
actual_reasoning_effort: medium
fallback_reason: "Persistent tester route is pinned to Terra/medium; launch result exposes task identity only."
model_fallback: false
last_verified: 2026-08-04
updated: 2026-08-04
write_scope:
  - "tests/unit/reconciliation_patterns/test_feedback_graph.py"
  - "tests/integration/test_pattern_registry_persistence.py"
source_paths:
  - "tests/unit/reconciliation_patterns/test_feedback_graph.py"
  - "tests/integration/test_pattern_registry_persistence.py"
depends_on:
  - "reconciliation-wave4-conflict-contract-recovery"
tags:
  - "task/tests"
  - "status/draft"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 4 conflict recovery adversarial tests

## Goal

Encode every prior P1/P2 persistence probe: conflict states and atomicity,
operation replay, tamper, failpoint, concurrency and unsafe paths.

## Completion evidence

- Changed paths: `tests/unit/reconciliation_patterns/test_feedback_graph.py`; `tests/integration/test_pattern_registry_persistence.py`; this task card.
- Commands and tests run: focused graph/persistence/contract `48 passed`;
  combined Wave 1-4 relevant suite `234 passed`; scoped Ruff and format checks
  passed.
- Result: covers observed authoritative outcomes, path safety, exact plan replay,
  concurrent next revisions, owner-approved and active conflicts, missing and
  partial conflict revisions, injected record/event/edge rollback, canonical
  payload and indexed-column tamper, orphan events and invalid lifecycle jumps.
- Constructor and post-open inode replacement regressions verify fail-closed
  `PATH_RACE` before mutation and before every later read/write.
- Risks or follow-up: focused evidence is green.

## Handoff

Leave in `review`; production fixes belong to recovery implementation owner.
