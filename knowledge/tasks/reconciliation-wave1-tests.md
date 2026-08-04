---
type: task
status: blocked
work_id: reconciliation-wave1-v1
role: worker
agent_role: tester
owner: "wave1-tests"
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
launch_status: inherited
actual_model: gpt-5.6-terra
actual_reasoning_effort: medium
fallback_reason: "Executed through the inherited tester route; no separate runtime confirmation was exposed."
model_fallback: false
last_verified: 2026-08-03
updated: 2026-08-03
write_scope:
  - "tests/unit/work_semantics"
  - "tests/contract/test_work_semantics_contract.py"
source_paths:
  - "tests/unit/work_semantics"
  - "tests/contract/test_work_semantics_contract.py"
depends_on:
  - reconciliation-wave1-core
tags:
  - "task/implementation"
  - "status/draft"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 1 normalization ontology and unit tests

## Goal

Prove the accepted Wave 1 public contract with golden normalization, homograph,
typo-boundary, multi-label/conflict, unit compatibility, unknown-unit isolation
and legacy exact-ID non-regression tests.

## Scope and instructions

- Modify only `write_scope` paths.
- Depend on the reviewed `reconciliation-wave1-core` implementation; tests may
  not change production code.
- Do not stage, commit or push anything.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: `tests/unit/work_semantics/test_canonicalization.py`,
  `tests/unit/work_semantics/test_ontology.py`,
  `tests/contract/test_work_semantics_contract.py`.
- Commands and tests run:
  `uv run ruff format --check tests/unit/work_semantics tests/contract/test_work_semantics_contract.py`;
  `uv run ruff check tests/unit/work_semantics tests/contract/test_work_semantics_contract.py`;
  `uv run pytest -q tests/unit/work_semantics tests/contract/test_work_semantics_contract.py`;
  `uv run pytest -q tests/unit/reconciliation_grouping tests/contract/test_reconciliation_grouping_contract.py`;
  `git diff --check -- tests/unit/work_semantics tests/contract/test_work_semantics_contract.py knowledge/tasks/reconciliation-wave1-tests.md`.
- Result: formatting, lint, legacy grouping checks (18 passed) and diff check passed.
  Focused Wave 1 suite has 35 passed and 1 expected contract failure:
  supply plus installation is incorrectly returned as an action conflict.
- Risks or follow-up: production owner must remove the unsupported
  supply/installation conflict before the focused suite can pass.

## Handoff

Superseded by `reconciliation-wave1-remediation-tests` after the final audit.
