---
type: task
status: done
work_id: reconciliation-wave2-remediation-v1
role: worker
agent_role: tester
owner: "wave2-remediation-tests"
profile: L1
routing_grade: P3
progress_revision: 2
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "L1 compatibility profile maps to P3."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: inherited
actual_model: gpt-5.6-terra
actual_reasoning_effort: medium
fallback_reason: "Subagent inherited the parent-assigned Terra route."
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
  - "reconciliation-wave2-remediation-core"
tags:
  - "task/implementation"
  - "status/draft"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 2 audit regression tests

## Goal

Add regression coverage for every accepted audit finding and frozen full legacy
group/version/feedback/package-key snapshots.

## Scope and instructions

- Modify only `write_scope` paths.
- Cover numero NFKC and compact standards, Wave 1 scoped aliases/typo/dashes,
  object scope positive/negative, malformed explicit markers/manual flag,
  literal sentinel collision, exact type hints/models and full legacy snapshots.
- Do not edit production/config or use Git.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: `tests/unit/work_semantics/test_typed_slots.py`,
  `tests/unit/work_semantics/test_semantic_skeleton.py`,
  `tests/contract/test_work_semantics_wave2_contract.py`.
- Commands and tests run:
  `.venv/bin/pytest -q tests/unit/work_semantics/test_typed_slots.py
  tests/unit/work_semantics/test_semantic_skeleton.py
  tests/contract/test_work_semantics_wave2_contract.py` — `49 passed`;
  `.venv/bin/pytest -q tests/unit/work_semantics
  tests/contract/test_work_semantics_contract.py
  tests/contract/test_work_semantics_wave2_contract.py
  tests/unit/reconciliation_review tests/unit/reconciliation_grouping` —
  `113 passed`; `.venv/bin/ruff check ...` and
  `.venv/bin/ruff format --check ...` — passed.
- Result: regression tests freeze all eight Wave 2 audit findings, including
  NFKC `No`/`№`, compact standards, scoped Wave 1 composition, object scopes,
  malformed markers, collision-safe masking, exact public models and full
  legacy group/feedback/feature/family/package/context snapshots.
- Risks or follow-up: full repository suite is outside this isolated Wave 2
  scope; relevant legacy snapshots and scoped suites are accepted.

## Handoff

Leave this card in `review` until orchestration accepts the result.
