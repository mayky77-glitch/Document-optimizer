---
type: task
status: superseded
work_id: reconciliation-wave3-final-remediation-v1
role: worker
agent_role: tester
owner: "wave3-final-tests"
profile: L1
routing_grade: P3
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Exact regression coverage for P6 re-audit defects"
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
  - "reconciliation-wave3-audit"
tags:
  - "task/implementation"
  - "status/draft"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 3 final adversarial tests

## Goal

Freeze every residual P6 re-audit defect with independent public-API and CLI
regression tests.

## Scope and instructions

- Modify only `write_scope` paths.
- Cover malformed nested corpus values, proposal/outcome invariants and exit codes.
- Assert exact profiler meanings, denominators, ratios and warning behavior.
- Assert no miner false positives, scope leaks or below-threshold candidates.
- Assert numeric evaluator atom/support/contradiction/agreement metrics.
- Assert privacy fragments for filenames, formulas, cells and comments.
- Assert exact `CODE: message`, `--top 0` and `--min-support-atoms 0` usage behavior.
- Use public API/CLI only; do not duplicate production private helpers.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: the four owned Wave 3 unit/contract test files.
- Commands and tests run: focused pytest (`30 passed in 1.09s`); Ruff check and
  format check for all four files (`All checks passed`, `4 files already
  formatted`).
- Result: public API/CLI regressions added for malformed nested inputs,
  outcome/candidate invariants, semantic identity slots, profiler denominator
  and privacy classes, evaluator atom metrics, and exact CLI failures/usage.
- Risks or follow-up: no remaining focused-test defect after the core handoff.

## Handoff

Leave this card in `review` until orchestration accepts the result.
