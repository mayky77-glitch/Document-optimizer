---
type: task
status: superseded
work_id: reconciliation-wave3-remediation-v1
role: worker
agent_role: developer
owner: "wave3-remediation-core"
profile: L2
routing_grade: P4
progress_revision: 1
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Nine localized but algorithmically coupled findings map to P4."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: inherited
actual_model: gpt-5.6-terra
actual_reasoning_effort: high
fallback_reason: "Reused the Wave 3 write-capable thread due runtime thread limit."
model_fallback: false
last_verified: 2026-08-03
updated: 2026-08-04
write_scope:
  - src/report_processor/reconciliation_patterns/offline.py
  - scripts/profile_reconciliation_corpus.py
  - scripts/mine_reconciliation_patterns.py
  - scripts/evaluate_reconciliation_patterns.py
source_paths:
  - knowledge/tasks/reconciliation-wave3-contract.md
  - knowledge/tasks/reconciliation-wave3-audit.md
depends_on:
  - reconciliation-wave3-audit
tags:
  - "task/implementation"
  - "status/draft"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 3 audit remediation core

## Goal

Close all nine accepted audit finding groups without weakening the frozen
confirmed-only, privacy or Wave 3/Wave 5 boundaries.

## Scope and instructions

- Modify only `write_scope`; no tests/config/legacy/Git edits.
- Implement exact schemas/deep immutability/semantic identity and reject raw
  malformed types as controlled input errors.
- Rebuild profiler metrics to their frozen definitions.
- Enforce conservative candidate eligibility, complete hard scope and
  candidate-specific support/contradictions without fabricated candidates.
- Rebuild evaluator on deduplicated proposal/scope atoms and expected outcomes.
- Prevent path/filename value leakage, candidate bypass and input overwrite.
- Make writes short-write safe/failure preserving and CLI output exact.
- Leave status `review` with exact evidence.

## Completion evidence

- Changed paths:
  - `src/report_processor/reconciliation_patterns/offline.py`
  - `scripts/profile_reconciliation_corpus.py`
  - `scripts/mine_reconciliation_patterns.py`
  - `scripts/evaluate_reconciliation_patterns.py`
- Commands and tests run:
  - `.venv/bin/ruff format` and `.venv/bin/ruff check` on the four owned paths: passed.
  - `PYTHONPATH=src .venv/bin/pytest -q tests/unit/reconciliation_patterns tests/contract/test_profile_reconciliation_corpus_contract.py tests/contract/test_mine_reconciliation_patterns_contract.py tests/contract/test_evaluate_reconciliation_patterns_contract.py`: `16 passed`.
  - `PYTHONPATH=src .venv/bin/pytest -q tests/unit/work_semantics tests/contract/test_work_semantics_contract.py tests/contract/test_work_semantics_wave2_contract.py tests/unit/reconciliation_grouping tests/unit/reconciliation_review`: `121 passed`.
  - Frozen/slotted public Wave 3 profile/evaluation nested-model probe: passed.
- Result:
  - Public profiler/evaluator sections are frozen typed dataclasses and tuples; serialization alone creates fresh plain JSON mappings.
  - Profiler uses review-relevant coverage denominators, deduplicated token/ngram/ontology/manual/rule metrics and deterministic rational ratios.
  - Miner partitions every proposal by complete semantic scope, keeps links lexical-only, excludes private rows, records candidate-local contradictions, and prevents tautological normalization rewrites.
  - Evaluator separates predicate from complete scope matching and reports atom-deduplicated unresolved, parse-warning, contradiction and hard-boundary metrics with exact agreement ratios.
- Risks or follow-up:
  - Critical-modifier proposals retain the frozen compact modifier shape; their intentionally broad lexical predicate is made visible as `hard_boundary_mismatch` by the descriptive evaluator and remains owner-review-only.

## Handoff

Leave this card in `review` until orchestration accepts the result.
