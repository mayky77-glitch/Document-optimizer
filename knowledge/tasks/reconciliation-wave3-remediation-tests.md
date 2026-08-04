---
type: task
status: superseded
work_id: reconciliation-wave3-remediation-tests-v1
role: worker
agent_role: tester
owner: "wave3-remediation-tests"
profile: L1
routing_grade: P3
progress_revision: 1
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Adversarial deterministic contract regression tests map to P3."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: inherited
actual_model: gpt-5.6-terra
actual_reasoning_effort: high
fallback_reason: "Serialized on the existing Terra/high write-capable thread due runtime thread limit."
model_fallback: false
last_verified: 2026-08-03
updated: 2026-08-04
write_scope:
  - tests/unit/reconciliation_patterns/test_offline.py
  - tests/contract/test_profile_reconciliation_corpus_contract.py
  - tests/contract/test_mine_reconciliation_patterns_contract.py
  - tests/contract/test_evaluate_reconciliation_patterns_contract.py
source_paths:
  - knowledge/tasks/reconciliation-wave3-contract.md
  - knowledge/tasks/reconciliation-wave3-audit.md
depends_on:
  - reconciliation-wave3-remediation-core
tags:
  - "task/implementation"
  - "status/draft"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 3 audit regression tests

## Goal

Freeze every accepted audit finding with independent, adversarial synthetic tests.

## Scope and instructions

- Modify only test `write_scope`; no production/config/Git edits.
- Avoid private production helpers when constructing fixtures.
- Cover exact profiler definitions, conservative candidates/hard scope,
  contradictory evaluator atoms, deep immutability, tampered candidate data,
  privacy values, short writes/failure preservation/input-output alias and CLI.
- Leave status `review` with exact evidence.

## Completion evidence

- Changed paths:
  - `tests/unit/reconciliation_patterns/test_offline.py`
  - `tests/contract/test_profile_reconciliation_corpus_contract.py`
  - `tests/contract/test_mine_reconciliation_patterns_contract.py`
  - `tests/contract/test_evaluate_reconciliation_patterns_contract.py`
  - `knowledge/tasks/reconciliation-wave3-remediation-tests.md`
- Commands and tests run:
  - `.venv/bin/ruff format --check tests/unit/reconciliation_patterns/test_offline.py tests/contract/test_profile_reconciliation_corpus_contract.py tests/contract/test_mine_reconciliation_patterns_contract.py tests/contract/test_evaluate_reconciliation_patterns_contract.py`: passed.
  - `.venv/bin/ruff check tests/unit/reconciliation_patterns/test_offline.py tests/contract/test_profile_reconciliation_corpus_contract.py tests/contract/test_mine_reconciliation_patterns_contract.py tests/contract/test_evaluate_reconciliation_patterns_contract.py`: passed.
  - `PYTHONPATH=src .venv/bin/pytest -q tests/unit/reconciliation_patterns tests/contract/test_profile_reconciliation_corpus_contract.py tests/contract/test_mine_reconciliation_patterns_contract.py tests/contract/test_evaluate_reconciliation_patterns_contract.py`: `24 passed in 0.80s`.
- Result:
  - Public-only synthetic corpus construction replaces private parser/material fixture dependencies.
  - Added regression coverage for deep public immutability, candidate ID/evidence/support-type tampering, controlled serialization errors, private-value absence, short write retry/failure preservation, and controlled CLIs for all three entry points.
- Risks or follow-up:
  - Exact domain-specific profiler/miner/evaluator partitions remain dependent on the remediation core's focused acceptance suite; no production behavior was changed from this test scope.

## Handoff

Leave this card in `review` until orchestration accepts the result.
