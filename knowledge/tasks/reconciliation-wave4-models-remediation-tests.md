---
type: task
status: superseded
work_id: reconciliation-wave4-models-remediation-v1
role: worker
agent_role: tester
owner: "wave4-models-remediation-tests"
profile: L1
routing_grade: P3
progress_revision: 1
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Independent adversarial coverage for four accepted P6 findings"
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: inherited
actual_model: gpt-5.6-terra
actual_reasoning_effort: medium
fallback_reason: "Persistent tester route is pinned to Terra/medium; launch result exposes task identity only."
model_fallback: false
last_verified: 2026-08-04
updated: 2026-08-04
write_scope:
  - "tests/contract/test_pattern_registry_contract.py"
source_paths:
  - "tests/contract/test_pattern_registry_contract.py"
depends_on:
  - "reconciliation-wave4-models-audit"
tags:
  - "task/implementation"
  - "status/draft"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 4 model audit regression tests

## Goal

Freeze every P6 model finding with adversarial public constructor/loader,
lifecycle and relation-semantic tests.

## Scope and instructions

- Modify only `write_scope` paths.
- Build full lifecycle records including future imported active state and rollback.
- Tamper candidate IDs/evidence/scope/proposal/outcome/support invariants.
- Exercise must/cannot/hard-negative outcomes, direction, reasons and provenance.
- Recursively inspect instance graphs and consequential fingerprint changes.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: `tests/contract/test_pattern_registry_contract.py`; this task card.
- Commands and tests run:
  - `uv run ruff format tests/contract/test_pattern_registry_contract.py && uv run ruff check tests/contract/test_pattern_registry_contract.py` — passed.
  - `uv run pytest -q tests/contract/test_pattern_registry_contract.py` — 12 passed.
  - `uv run pytest -q tests/contract/test_profile_reconciliation_corpus_contract.py tests/contract/test_mine_reconciliation_patterns_contract.py tests/contract/test_evaluate_reconciliation_patterns_contract.py` — 17 passed.
- Result: P6 regression coverage freezes lifecycle/rollback/approval boundaries, Wave 5-only activation, Wave 3 candidate identity/evidence tampering, recursive immutability, consequential fingerprints, typed authoritative feedback provenance and relation semantics, controlled malformed input, and logical hard-negative schema.
- Risks or follow-up: no outstanding focused-test failures.

## Handoff

Leave this card in `review` until orchestration accepts the result.
