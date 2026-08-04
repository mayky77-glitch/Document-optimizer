---
type: task
status: superseded
work_id: reconciliation-wave3-v1
role: worker
agent_role: tester
owner: "wave3-tests"
profile: L1
routing_grade: P3
progress_revision: 2
state_fingerprint: "wave3-tests-fixture-remediation-v1"
no_progress_count: 0
circuit_state: closed
routing_reason: "Bounded deterministic contract tests map to P3."
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
  - tests/unit/reconciliation_patterns/test_offline.py
  - tests/contract/test_profile_reconciliation_corpus_contract.py
  - tests/contract/test_mine_reconciliation_patterns_contract.py
  - tests/contract/test_evaluate_reconciliation_patterns_contract.py
source_paths:
  - knowledge/tasks/reconciliation-wave3-contract.md
depends_on:
  - reconciliation-wave3-contract
tags:
  - "task/implementation"
  - "status/draft"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 3 contract and CLI tests

## Goal

Prove the full frozen acceptance matrix with synthetic, privacy-safe data only.

## Scope and instructions

- Modify only `write_scope` paths; no production/config/fixture/Git edits.
- Build fixtures in test code with synthetic terms and opaque hashes.
- Cover shuffled byte determinism, dedup/contradictions, confirmed-only support,
  all profile sections/seven candidate kinds, same-corpus evaluation, strict
  privacy/schema/errors and safe output behavior.
- Assert no network/Qdrant/openpyxl/AI or legacy integration.
- Leave status `review` with exact evidence.

## Completion evidence

- Changed paths: the four Wave 3 tests in `write_scope` only.
- Commands and tests run: `.venv/bin/ruff format`; `.venv/bin/ruff check`;
  focused Wave 3 pytest; Wave 1/2 work-semantics unit and contract suites.
- Result: fixtures now compute the frozen canonical row fingerprint and put
  bare cable sections inside `object_kind="cable"`. Ruff passes. Focused Wave
  3 suite has `12 passed, 4 failed`; failures are retained as contract evidence,
  not worked around in tests.
- Risks or follow-up: production remediation is required for the remaining
  exact public contract: `critical_modifier` must not be gated by lexical-near
  when exactly one uncovered token partitions outcomes; public `CandidateKind`,
  complete `PatternScope`/`SupportSummary`/candidate payload fields, and exact
  evaluator deduplicated-count/rational-agreement fields are absent. The tests
  cover strict fields/versions, nonfinite JSON, private output fields, mode
  0600/symlink/overwrite, confirmed atom behaviour, profile sections, rule
  coverage, evaluator non-promotion and isolation.

## Handoff

Leave this card in `review` until orchestration accepts the result.
