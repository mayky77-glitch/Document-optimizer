---
type: task
status: superseded
work_id: reconciliation-wave3-final-remediation-v1
role: worker
agent_role: developer
owner: "wave3-final-core"
profile: L2
routing_grade: P4
progress_revision: 1
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "P6 re-audit found coupled schema profiler miner evaluator privacy CLI defects"
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: confirmed
actual_model: gpt-5.6-terra
actual_reasoning_effort: high
fallback_reason: ""
model_fallback: false
last_verified: 2026-08-04
updated: 2026-08-04
write_scope:
  - "src/report_processor/reconciliation_patterns/offline.py"
  - "scripts/profile_reconciliation_corpus.py"
  - "scripts/mine_reconciliation_patterns.py"
  - "scripts/evaluate_reconciliation_patterns.py"
source_paths:
  - "src/report_processor/reconciliation_patterns/offline.py"
  - "scripts/profile_reconciliation_corpus.py"
  - "scripts/mine_reconciliation_patterns.py"
  - "scripts/evaluate_reconciliation_patterns.py"
depends_on:
  - "reconciliation-wave3-audit"
tags:
  - "task/implementation"
  - "status/review"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 3 final production remediation

## Goal

Close every remaining actionable defect from the Wave 3 P6 re-audit without
activating candidates or changing legacy grouping.

## Scope and instructions

- Modify only `write_scope` paths.
- Enforce controlled corpus/candidate schema errors and exact proposal/outcome invariants.
- Correct profiler token/denominator/variant/full-coverage definitions.
- Enforce per-candidate support threshold and incomplete-scope risk in miner.
- Count contradictory atoms and exact outcome agreement in evaluator.
- Reject all frozen privacy classes: paths, filenames, formulas, cells, comments.
- Emit CLI usage errors as exit 2 and stable failures as `CODE: message`.
- Preserve safe-write, deep immutability, semantic identity and offline-only boundaries.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths:
  - `src/report_processor/reconciliation_patterns/offline.py`
  - `scripts/profile_reconciliation_corpus.py`
  - `scripts/mine_reconciliation_patterns.py`
  - `scripts/evaluate_reconciliation_patterns.py`
- Commands and tests run:
  - `.venv/bin/ruff format --check` and `.venv/bin/ruff check` on the Wave 3
    core and assigned regression files: passed.
  - `PYTHONPATH=src .venv/bin/pytest -q tests/unit/reconciliation_patterns
    tests/contract/test_profile_reconciliation_corpus_contract.py
    tests/contract/test_mine_reconciliation_patterns_contract.py
    tests/contract/test_evaluate_reconciliation_patterns_contract.py`:
    `30 passed`.
  - `PYTHONPATH=src .venv/bin/pytest -q tests/unit/work_semantics
    tests/contract/test_work_semantics_contract.py
    tests/contract/test_work_semantics_wave2_contract.py
    tests/unit/reconciliation_grouping tests/unit/reconciliation_review`:
    `121 passed`.
- Result:
  - Corpus and candidate nested shapes fail as controlled schema errors; all
    seven proposals, expected outcomes, support invariants, and enums are
    validated before construction.
  - The profiler keeps all review-relevant rows in aggregate denominators,
    preserves safe audit-form variants, recognizes ontology tokens, and makes
    warnings/conflicts ineligible for full coverage.
  - Mining emits only threshold-qualified candidates, requires bilateral
    category-normalization evidence, and marks hard scope leakage with
    `incomplete_scope`; evaluation deduplicates and reports contradictory atoms
    separately from usable confirmed support.
  - Serializers reject frozen privacy classes without altering aggregates; CLIs
    use `CODE: message` and argparse exit 2 for non-positive numeric options.
- Risks or follow-up:
  - Outputs remain deliberately private local artifacts; aggressive filename,
    formula, cell, comment, and fragment screening may suppress a descriptive
    text value rather than risk disclosure.

## Handoff

Leave this card in `review` until orchestration accepts the result.
