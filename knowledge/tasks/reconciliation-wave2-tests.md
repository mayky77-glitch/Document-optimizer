---
type: task
status: blocked
work_id: reconciliation-wave2-v1
role: worker
agent_role: tester
owner: "wave2-tests"
profile: L1
routing_grade: P3
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "L1 compatibility profile maps to P3."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: confirmed
actual_model: gpt-5.6-terra
actual_reasoning_effort: medium
fallback_reason: ""
model_fallback: false
last_verified: 2026-08-03
updated: 2026-08-03
write_scope:
  - "tests/unit/work_semantics/test_typed_slots.py"
  - "tests/unit/work_semantics/test_semantic_skeleton.py"
  - "tests/contract/test_work_semantics_wave2_contract.py"
source_paths:
  - "tests/unit/work_semantics/test_typed_slots.py"
  - "tests/unit/work_semantics/test_semantic_skeleton.py"
  - "tests/contract/test_work_semantics_wave2_contract.py"
depends_on:
  - "reconciliation-wave2-core"
tags:
  - "task/implementation"
  - "status/draft"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 2 typed slots and skeleton tests

## Goal

Prove every accepted Wave 2 parser/skeleton invariant and direct-import legacy
non-regression behavior.

## Scope and instructions

- Modify only `write_scope` paths.
- Requirement-driven coverage for all slot kinds, impacts, spans, precedence,
  ambiguity/conflict codes, deterministic immutable output, masking and
  document-index nonsemantic behavior.
- Do not edit production/config or use Git.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: three assigned Wave 2 test files only.
- Commands and tests run: Wave 2 31 passed; accepted Wave 1 semantics 45 passed;
  scoped Ruff/format passed.
- Result: all frozen slot/skeleton and direct-import legacy-isolation cases pass.
- Risks or follow-up: final read-only audit pending.

## Handoff

Superseded by `reconciliation-wave2-remediation-tests` after final audit.
