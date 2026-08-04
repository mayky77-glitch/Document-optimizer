---
type: task
status: superseded
work_id: reconciliation-wave4-models-v1
role: worker
agent_role: tester
owner: "wave4-models-tests"
profile: L1
routing_grade: P3
progress_revision: 1
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Independent exact public contract and immutability tests"
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
  - "reconciliation-wave4-contract"
tags:
  - "task/implementation"
  - "status/draft"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 4 pattern model contract tests

## Goal

Freeze exact Wave 4 model fields, versions, deep immutability, validation and
fingerprint behavior with independent contract tests.

## Scope and instructions

- Modify only `write_scope` paths.
- Use public imports only; do not edit production or copy private helpers.
- Cover consequential-field fingerprints, malformed nested values and state metadata.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: `tests/contract/test_pattern_registry_contract.py`; this task card.
- Commands and tests run:
  - `uv run ruff format tests/contract/test_pattern_registry_contract.py && uv run ruff check tests/contract/test_pattern_registry_contract.py && uv run ruff format --check tests/contract/test_pattern_registry_contract.py` — passed.
  - `uv run pytest -q tests/contract/test_pattern_registry_contract.py` — collection blocked before the parallel-owned `pattern_models.py` exists (`ImportError`).
  - `uv run pytest -q tests/contract/test_profile_reconciliation_corpus_contract.py tests/contract/test_mine_reconciliation_patterns_contract.py tests/contract/test_evaluate_reconciliation_patterns_contract.py` — 17 passed.
- Result: independent public contract coverage pins versions, lifecycle, immutable field sets, candidate identity/support retention, feedback confirmations/edges, canonical fingerprints, malformed data, no-runtime imports and hard-negative schema exclusions.
- Risks or follow-up: rerun the focused Wave 4 test after the core module appears. The frozen tester requirement names graph endpoint/reason/direction models; core was notified because its preliminary API had no explicit models for those concepts.

## Handoff

Leave this card in `review` until orchestration accepts the result.
