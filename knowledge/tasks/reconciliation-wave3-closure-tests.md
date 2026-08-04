---
type: task
status: superseded
work_id: reconciliation-wave3-closure-v1
role: worker
agent_role: tester
owner: "wave3-closure-tests"
profile: L1
routing_grade: P3
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Exact public regression tests for four final P6 probes"
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: confirmed
actual_model: gpt-5.6-terra
actual_reasoning_effort: medium
fallback_reason: ""
model_fallback: false
last_verified: 2026-08-04
updated: 2026-08-04
write_scope:
  - "tests/unit/reconciliation_patterns/test_offline.py"
  - "tests/contract/test_profile_reconciliation_corpus_contract.py"
  - "tests/contract/test_mine_reconciliation_patterns_contract.py"
  - "tests/contract/test_evaluate_reconciliation_patterns_contract.py"
source_paths:
  - "tests/unit/reconciliation_patterns/test_offline.py"
  - "tests/contract/test_profile_reconciliation_corpus_contract.py"
  - "tests/contract/test_mine_reconciliation_patterns_contract.py"
  - "tests/contract/test_evaluate_reconciliation_patterns_contract.py"
depends_on:
  - "reconciliation-wave3-final-audit"
tags:
  - "task/implementation"
  - "status/draft"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 3 closure regression tests

## Goal

Freeze every final P6 probe with exact public-API and CLI regression tests.

## Scope and instructions

- Modify only `write_scope` paths.
- Cover typed parameter near-pairs and non-adjacent unknown-token n-gram rejection.
- Cover archive filenames, row coordinates, provenance, source digest and quantity fragments.
- Cover invariant exit 5 and candidate-specific malformed-input codes.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: all four assigned Wave 3 unit/contract test files.
- Commands and tests run: `.venv/bin/ruff check` and `.venv/bin/ruff format
  --check` over those four files (passed); focused pytest over those same files
  (`35 passed in 1.10s`).
- Result: public regressions cover structural parameter near pairs and raw-value
  redaction, adjacent-only uncovered n-grams, final privacy fragments, exact
  exit-5 colon protocol, and candidate header/top/nested schema rejection.
- Risks or follow-up: none from focused closure coverage.

## Handoff

Leave this card in `review` until orchestration accepts the result.
