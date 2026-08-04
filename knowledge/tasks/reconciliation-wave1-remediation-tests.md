---
type: task
status: done
work_id: reconciliation-wave1-remediation-v1
role: worker
agent_role: tester
owner: "wave1-remediation-tests"
profile: L1
routing_grade: P3
progress_revision: 1
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
  - "tests/unit/work_semantics"
  - "tests/contract/test_work_semantics_contract.py"
source_paths:
  - "tests/unit/work_semantics"
  - "tests/contract/test_work_semantics_contract.py"
depends_on:
  - "reconciliation-wave1-remediation-core"
  - "reconciliation-wave1-remediation-packaging"
tags:
  - "task/implementation"
  - "status/review"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 1 audit regression tests

## Goal

Add regression tests for all seven accepted audit findings, including installed
wheel import and real generated legacy identity snapshots.

## Scope and instructions

- Modify only `write_scope` paths.
- Tests must cover scoped alias end-to-end, unknown-unit separator collisions,
  compact DN/PN homographs, phrase positive/negative matching, JSON version and
  conflict-pair validation, wheel resource import, generated legacy group
  ID/version, feedback keys and five-position package tuple shape.
- Do not edit production/config and do not perform Git operations.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: `tests/unit/work_semantics/test_canonicalization.py`,
  `tests/unit/work_semantics/test_ontology.py`,
  `tests/contract/test_work_semantics_contract.py`.
- Commands and tests run:
  - `.venv/bin/ruff check tests/unit/work_semantics tests/contract/test_work_semantics_contract.py`
    — passed.
  - `.venv/bin/ruff format --check tests/unit/work_semantics tests/contract/test_work_semantics_contract.py`
    — passed.
  - `.venv/bin/pytest -q tests/unit/work_semantics tests/contract/test_work_semantics_contract.py`
    — 45 passed.
  - `.venv/bin/pytest -q tests/unit/reconciliation_review tests/unit/reconciliation_grouping tests/contract/test_reconciliation_grouping_contract.py`
    — 20 passed.
  - `.venv/bin/ruff check tests && .venv/bin/ruff format --check tests` — stopped at
    three pre-existing `E501` violations in
    `tests/integration/test_drawing_card_ui_contract.py` (outside this scope).
- Result: regressions cover scoped aliases end-to-end, unknown-unit identity,
  compact DN/PN spelling, phrase/negative matching, resource schema/version and
  conflicts, isolated wheel resource import, and legacy group/feedback/package
  snapshots before and after semantics import.
- Risks or follow-up: global Ruff requires a separate owner for the three
  unrelated integration-test line-length violations.

## Handoff

Leave this card in `review` until orchestration accepts the result.
